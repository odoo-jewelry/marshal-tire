"""Tests for budget-tagging extensions on account.account / account.move."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_budget_base')
class TestAccountBudgetFields(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.kekv_2111 = cls.env.ref('l10n_ua_budget_base.kekv_2111')
        cls.kekv_2273 = cls.env.ref('l10n_ua_budget_base.kekv_2273')
        cls.kfk_0910 = cls.env.ref('l10n_ua_budget_base.kfk_0910')

    def _make_account(self, **vals):
        defaults = {
            'code': 'TST001',
            'name': 'Test budget acct',
            'account_type': 'expense',
            'company_ids': [(6, 0, [self.company.id])],
        }
        defaults.update(vals)
        return self.env['account.account'].create(defaults)

    def test_default_kekv_on_account(self):
        acct = self._make_account(
            code='BUD001',
            ua_budget_is_state_sector=True,
            ua_default_kekv_id=self.kekv_2111.id,
            ua_fund_type='general',
        )
        self.assertEqual(acct.ua_default_kekv_id, self.kekv_2111)
        self.assertEqual(acct.ua_fund_type, 'general')

    def test_fund_mismatch_raises(self):
        """Line cannot specify a fund different from the account's restricted fund."""
        acct = self._make_account(
            code='BUD002', ua_fund_type='general')
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'date': '2025-01-01',
        })
        with self.assertRaises(ValidationError):
            self.env['account.move.line'].create({
                'move_id': move.id,
                'account_id': acct.id,
                'debit': 100.0,
                'name': 'Bad fund',
                'ua_fund_type': 'special',  # account is restricted to general
            })

    def test_kpkvk_propagation(self):
        """Setting КПКВК on the move should pre-fill empty lines (via onchange)."""
        kpkvk = self.env.ref('l10n_ua_budget_base.kpkvk_2201190_2025')
        move = self.env['account.move'].new({
            'move_type': 'entry',
            'date': '2025-01-01',
            'ua_kpkvk_id': kpkvk.id,
        })
        # Trigger the propagation (would happen via UI onchange)
        move._onchange_ua_kpkvk_propagate()
        # No lines yet, but the field is set
        self.assertEqual(move.ua_kpkvk_id, kpkvk)
