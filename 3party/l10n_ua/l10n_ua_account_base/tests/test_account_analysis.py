"""Тести аналізу рахунку (#133).

Покриття:
- Обороти рахунку в розрізі кореспондуючих рахунків
- Початкове/кінцеве сальдо, підсумки
- Розподіл на кілька кореспондентів (багаторядкова проводка)
- Валідація періоду
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAccountAnalysis(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].create({
            'name': 'Аналіз тест', 'code': 'ANLZ',
            'type': 'general', 'company_id': cls.company.id})
        cls.acc_a = cls.env['account.account'].create({
            'name': 'Аналіз рахунок', 'code': 'ANLA',
            'account_type': 'asset_current',
            'company_ids': [(4, cls.company.id)]})
        cls.acc_b = cls.env['account.account'].create({
            'name': 'Корр B', 'code': 'ANLB', 'account_type': 'income',
            'company_ids': [(4, cls.company.id)]})
        cls.acc_c = cls.env['account.account'].create({
            'name': 'Корр C', 'code': 'ANLC', 'account_type': 'expense',
            'company_ids': [(4, cls.company.id)]})

    def _move(self, move_date, lines):
        """lines: list of (account, debit, credit)."""
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': move_date,
            'line_ids': [(0, 0, {'account_id': a.id, 'debit': d, 'credit': c})
                         for a, d, c in lines],
        })
        move.action_post()
        return move

    def _analysis(self):
        return self.env['l10n_ua.account.analysis'].create({
            'account_id': self.acc_a.id,
            'period_start': date(2025, 1, 1),
            'period_end': date(2025, 12, 31),
            'company_id': self.company.id,
        })

    def test_correspondence_turnover(self):
        # До періоду: Дт A 1000 / Кт B → сальдо A = 1000.
        self._move(date(2024, 12, 31), [(self.acc_a, 1000, 0), (self.acc_b, 0, 1000)])
        # У періоді: Дт A 500 / Кт B; Кт A 200 / Дт C.
        self._move(date(2025, 3, 1), [(self.acc_a, 500, 0), (self.acc_b, 0, 500)])
        self._move(date(2025, 6, 1), [(self.acc_c, 200, 0), (self.acc_a, 0, 200)])

        an = self._analysis()
        an.action_compute()

        self.assertAlmostEqual(an.opening_balance, 1000.0)
        self.assertAlmostEqual(an.total_debit, 500.0)
        self.assertAlmostEqual(an.total_credit, 200.0)
        self.assertAlmostEqual(an.closing_balance, 1300.0)

        line_b = an.line_ids.filtered(lambda l: l.corr_account_id == self.acc_b)
        line_c = an.line_ids.filtered(lambda l: l.corr_account_id == self.acc_c)
        # A дебетувався проти B на 500.
        self.assertAlmostEqual(line_b.turnover_debit, 500.0)
        self.assertAlmostEqual(line_b.turnover_credit, 0.0)
        # A кредитувався проти C на 200.
        self.assertAlmostEqual(line_c.turnover_credit, 200.0)
        self.assertAlmostEqual(line_c.turnover_debit, 0.0)

    def test_multi_correspondent_distribution(self):
        # Дт A 300 / Кт B 100 / Кт C 200 — розподіл пропорційно.
        self._move(date(2025, 4, 1), [
            (self.acc_a, 300, 0), (self.acc_b, 0, 100), (self.acc_c, 0, 200)])
        an = self._analysis()
        an.action_compute()
        line_b = an.line_ids.filtered(lambda l: l.corr_account_id == self.acc_b)
        line_c = an.line_ids.filtered(lambda l: l.corr_account_id == self.acc_c)
        self.assertAlmostEqual(line_b.turnover_debit, 100.0)
        self.assertAlmostEqual(line_c.turnover_debit, 200.0)
        self.assertAlmostEqual(an.total_debit, 300.0)

    def test_period_validation(self):
        an = self.env['l10n_ua.account.analysis'].create({
            'account_id': self.acc_a.id,
            'period_start': date(2025, 12, 31),
            'period_end': date(2025, 1, 1),
            'company_id': self.company.id,
        })
        with self.assertRaises(UserError):
            an.action_compute()
