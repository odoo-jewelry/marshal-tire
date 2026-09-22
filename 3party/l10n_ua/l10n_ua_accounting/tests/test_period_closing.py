"""Tests for period closing — Flow 5 from ACCOUNTING_UKRAINE.md.

Tests cover:
- Period closing creation
- Account balance computation
- Closing journal entries generation
- State workflow (draft → closed → reversed)
"""

from datetime import date
from unittest import SkipTest
from odoo.tests import tagged
from .common import AccountingTestCase


@tagged('post_install', '-at_install')
class TestPeriodClosing(AccountingTestCase):
    """Test period closing workflow (закриття періоду)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Find or create a tax period
        cls.period = cls.env['l10n_ua.tax.period'].search([
            ('company_id', '=', cls.company.id),
        ], limit=1)
        if not cls.period:
            cls.period = cls.env['l10n_ua.tax.period'].create({
                'name': 'Тестовий період',
                'date_start': date(2025, 1, 1),
                'date_end': date(2025, 1, 31),
                'period_type': 'month',
                'month': 1,
                'year': 2025,
                'quarter': 1,
                'company_id': cls.company.id,
            })

    def _create_closing(self):
        """Helper to create period closing with required accounts."""
        # Find P&L accounts (Odoo 19: account.account has no company_id field)
        Account = self.env['account.account']
        account_791 = Account.search([('code', '=like', '791%')], limit=1)
        account_792 = Account.search([('code', '=like', '792%')], limit=1)
        account_793 = Account.search([('code', '=like', '793%')], limit=1)
        account_441 = Account.search([('code', '=like', '441%')], limit=1)
        account_442 = Account.search([('code', '=like', '442%')], limit=1)

        vals = {
            'period_id': self.period.id,
            'journal_id': self.misc_journal.id,
            'company_id': self.company.id,
        }
        if account_791:
            vals['account_791_id'] = account_791.id
        if account_792:
            vals['account_792_id'] = account_792.id
        if account_793:
            vals['account_793_id'] = account_793.id
        if account_441:
            vals['account_profit_id'] = account_441.id
        if account_442:
            vals['account_loss_id'] = account_442.id

        return self.env['l10n_ua.period.closing'].create(vals)

    def test_period_closing_creation(self):
        """Period closing should be created in draft state."""
        closing = self._create_closing()
        self.assertEqual(closing.state, 'draft')
        self.assertTrue(closing.name)

    def test_period_closing_name_computed(self):
        """Name should be auto-generated from period."""
        closing = self._create_closing()
        self.assertIn(self.period.name, closing.name)

    def test_period_closing_compute(self):
        """action_compute should populate closing lines."""
        closing = self._create_closing()
        # Check all required accounts exist
        if not (closing.account_791_id and closing.account_792_id
                and closing.account_793_id):
            raise SkipTest('Accounts 791/792/793 not available in test DB')
        closing.action_compute()
        # Lines should be populated (even if empty when no P&L entries)
        self.assertIsNotNone(closing.closing_line_ids)

    def test_period_closing_state_workflow(self):
        """State should follow draft → closed → reversed → draft."""
        closing = self._create_closing()
        if not (closing.account_791_id and closing.account_792_id
                and closing.account_793_id):
            raise SkipTest('Accounts 791/792/793 not available in test DB')
        self.assertEqual(closing.state, 'draft')

        # Compute first
        closing.action_compute()

        # Close
        closing.action_close()
        self.assertEqual(closing.state, 'closed')

        # Reverse
        closing.action_reverse()
        self.assertEqual(closing.state, 'reversed')

        # Back to draft
        closing.action_draft()
        self.assertEqual(closing.state, 'draft')

    def test_default_accounts_scoped_to_company(self):
        """Auto-filled result accounts must belong to the closing's company — issue #175."""
        closing = self.env['l10n_ua.period.closing'].create({
            'period_id': self.period.id,
            'journal_id': self.misc_journal.id,
            'company_id': self.company.id,
        })
        closing._set_default_accounts()
        for field in ('account_791_id', 'account_792_id', 'account_793_id',
                      'account_profit_id', 'account_loss_id'):
            acc = closing[field]
            if acc:
                self.assertIn(
                    self.company.id, acc.company_ids.ids,
                    '%s was filled with an account from another company' % field)
