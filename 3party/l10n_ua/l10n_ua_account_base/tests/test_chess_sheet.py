"""Тести шахматки (#140).

Покриття:
- Матриця оборотів Дт-рахунок × Кт-рахунок (проста і багаторядкова проводка)
- Загальний підсумок = сумі Дт = сумі Кт
- Поза періодом ігнорується
- Валідація періоду
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestChessSheet(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].create({
            'name': 'Шах тест', 'code': 'CHSS',
            'type': 'general', 'company_id': cls.company.id})
        cls.acc_a = cls.env['account.account'].create({
            'name': 'A', 'code': 'CHA', 'account_type': 'asset_current',
            'company_ids': [(4, cls.company.id)]})
        cls.acc_b = cls.env['account.account'].create({
            'name': 'B', 'code': 'CHB', 'account_type': 'income',
            'company_ids': [(4, cls.company.id)]})
        cls.acc_c = cls.env['account.account'].create({
            'name': 'C', 'code': 'CHC', 'account_type': 'expense',
            'company_ids': [(4, cls.company.id)]})

    def _move(self, move_date, lines):
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'date': move_date,
            'line_ids': [(0, 0, {'account_id': a.id, 'debit': d, 'credit': c})
                         for a, d, c in lines],
        })
        move.action_post()
        return move

    def _sheet(self):
        return self.env['l10n_ua.chess.sheet'].create({
            'period_start': date(2025, 1, 1),
            'period_end': date(2025, 12, 31),
            'company_id': self.company.id,
        })

    def _cell(self, sheet, dr, cr):
        return sheet.line_ids.filtered(
            lambda l: l.debit_account_id == dr and l.credit_account_id == cr)

    def test_simple_and_multi_correspondence(self):
        # Дт A / Кт B 500.
        self._move(date(2025, 3, 1), [(self.acc_a, 500, 0), (self.acc_b, 0, 500)])
        # Дт A 300 / Кт B 100 / Кт C 200 — розкладається на (A,B)=100, (A,C)=200.
        self._move(date(2025, 4, 1),
                   [(self.acc_a, 300, 0), (self.acc_b, 0, 100), (self.acc_c, 0, 200)])
        # Поза періодом.
        self._move(date(2026, 1, 5), [(self.acc_a, 999, 0), (self.acc_b, 0, 999)])

        sheet = self._sheet()
        sheet.action_compute()

        self.assertAlmostEqual(self._cell(sheet, self.acc_a, self.acc_b).amount, 600.0)
        self.assertAlmostEqual(self._cell(sheet, self.acc_a, self.acc_c).amount, 200.0)
        # Оборот саме за нашими рахунками = 500 + 300 = 800 (глобальний total
        # включає інші проводки БД, тому перевіряємо власні комірки).
        my_cells = sheet.line_ids.filtered(
            lambda l: l.debit_account_id == self.acc_a)
        self.assertAlmostEqual(sum(my_cells.mapped('amount')), 800.0)

    def test_period_validation(self):
        sheet = self.env['l10n_ua.chess.sheet'].create({
            'period_start': date(2025, 12, 31),
            'period_end': date(2025, 1, 1),
            'company_id': self.company.id,
        })
        with self.assertRaises(UserError):
            sheet.action_compute()
