"""Tests for ua_state chart template installation."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_budget_chart_template')
class TestUaStateChartTemplate(TransactionCase):

    def test_template_data_available(self):
        """Calling the @template-decorated method returns the expected dict."""
        ChartTpl = self.env['account.chart.template']
        data = ChartTpl._get_ua_state_template_data()
        self.assertEqual(data['code_digits'], '4')
        self.assertIn('property_account_receivable_id', data)
        self.assertEqual(data['property_account_receivable_id'], 'ua_state_2117')

    def test_accounts_data_state_sector_flag(self):
        ChartTpl = self.env['account.chart.template']
        accounts = ChartTpl._get_ua_state_account_account()
        # Every account should be flagged as state-sector
        for xmlid, vals in accounts.items():
            self.assertTrue(
                vals.get('ua_budget_is_state_sector'),
                f"{xmlid} missing ua_budget_is_state_sector flag")
        # Key accounts must be present
        self.assertIn('ua_state_2313', accounts)  # Реєстраційні рахунки
        self.assertIn('ua_state_5511', accounts)  # Фінансові результати
        self.assertIn('ua_state_7011', accounts)  # Бюджетні асигнування
        self.assertIn('ua_state_8011', accounts)  # Оплата праці
        self.assertIn('ua_state_2411', accounts)  # Каса
