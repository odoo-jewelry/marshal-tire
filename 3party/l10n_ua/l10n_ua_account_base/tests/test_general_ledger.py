"""Тести Головної книги (#137).

Покриття:
- Початкове сальдо, помісячні обороти Дт/Кт, річні підсумки, кінцеве сальдо
- Рух поза роком ігнорується
- Валідація року
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestGeneralLedger(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].create({
            'name': 'ГК тест', 'code': 'GLDG',
            'type': 'general', 'company_id': cls.company.id})
        cls.acc_a = cls.env['account.account'].create({
            'name': 'ГК актив', 'code': 'GLA', 'account_type': 'asset_current',
            'company_ids': [(4, cls.company.id)]})
        cls.acc_b = cls.env['account.account'].create({
            'name': 'ГК дохід', 'code': 'GLB', 'account_type': 'income',
            'company_ids': [(4, cls.company.id)]})

    def _move(self, move_date, amount):
        move = self.env['account.move'].create({
            'move_type': 'entry', 'journal_id': self.journal.id,
            'date': move_date,
            'line_ids': [
                (0, 0, {'account_id': self.acc_a.id, 'debit': amount, 'credit': 0.0}),
                (0, 0, {'account_id': self.acc_b.id, 'debit': 0.0, 'credit': amount}),
            ],
        })
        move.action_post()
        return move

    def _ledger(self, year=2025):
        return self.env['l10n_ua.general.ledger'].create({
            'year': year, 'company_id': self.company.id})

    def _line(self, ledger, account):
        return ledger.line_ids.filtered(lambda l: l.account_id == account)

    def test_opening_monthly_closing(self):
        self._move(date(2024, 12, 31), 1000.0)  # opening (prior year)
        self._move(date(2025, 3, 15), 500.0)     # березень
        self._move(date(2025, 7, 10), 300.0)     # липень
        self._move(date(2026, 1, 5), 999.0)      # поза роком

        gl = self._ledger(2025)
        gl.action_compute()

        line_a = self._line(gl, self.acc_a)
        self.assertEqual(len(line_a), 1)
        self.assertAlmostEqual(line_a.opening_debit, 1000.0)
        self.assertAlmostEqual(line_a.m03_debit, 500.0)
        self.assertAlmostEqual(line_a.m07_debit, 300.0)
        self.assertAlmostEqual(line_a.m01_debit, 0.0)
        self.assertAlmostEqual(line_a.total_debit, 800.0)
        self.assertAlmostEqual(line_a.closing_debit, 1800.0)

        # Дзеркальний дохідний рахунок (кредит-сторона).
        line_b = self._line(gl, self.acc_b)
        self.assertAlmostEqual(line_b.m03_credit, 500.0)
        self.assertAlmostEqual(line_b.total_credit, 800.0)
        self.assertAlmostEqual(line_b.closing_credit, 1800.0)

    def test_year_validation(self):
        gl = self.env['l10n_ua.general.ledger'].create({
            'year': 0, 'company_id': self.company.id})
        with self.assertRaises(UserError):
            gl.action_compute()
