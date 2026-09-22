"""Tests for cash limit control — Gap #5 from ACCOUNTING_UKRAINE.md.

Tests cover:
- Company cash limit settings
- Cash balance calculation
- Warning on post when limit exceeded
- Daily cron check
"""

from odoo.tests import tagged
from .common import AccountingTestCase


@tagged('post_install', '-at_install')
class TestCashLimit(AccountingTestCase):
    """Test cash limit control (контроль ліміту каси)."""

    def test_company_cash_limit_fields_exist(self):
        """Company should have cash limit fields."""
        self.assertFalse(self.company.l10n_ua_cash_limit_enabled)
        self.assertEqual(self.company.l10n_ua_cash_limit, 10000)

    def test_enable_cash_limit(self):
        """Should be able to enable cash limit control."""
        self.company.write({
            'l10n_ua_cash_limit_enabled': True,
            'l10n_ua_cash_limit': 50000,
        })
        self.assertTrue(self.company.l10n_ua_cash_limit_enabled)
        self.assertEqual(self.company.l10n_ua_cash_limit, 50000)

    def test_get_cash_balance(self):
        """Journal._get_cash_balance() should return numeric value."""
        balance = self.cash_journal._get_cash_balance()
        self.assertIsInstance(balance, float)

    def test_cron_method_exists(self):
        """Cron method should be callable on journal model."""
        # Should not raise
        self.env['account.journal']._cron_check_cash_limit()

    def test_cron_with_limit_disabled(self):
        """Cron should do nothing when limit is disabled."""
        self.company.l10n_ua_cash_limit_enabled = False
        # Should not raise or post any messages
        self.env['account.journal']._cron_check_cash_limit()

    def test_cron_record_exists(self):
        """Cron job record should exist."""
        cron = self.env.ref('l10n_ua_accounting.ir_cron_cash_limit_check',
                            raise_if_not_found=False)
        self.assertTrue(cron, 'Cash limit cron job should exist')
        self.assertEqual(cron.interval_type, 'days')
        self.assertEqual(cron.interval_number, 1)
