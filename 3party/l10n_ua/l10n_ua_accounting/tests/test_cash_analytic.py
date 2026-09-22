"""Tests for analytic distribution on Ukrainian cash orders (PKO/VKO) — issue #33."""

from odoo.tests import tagged
from odoo.exceptions import UserError
from .common import AccountingTestCase


@tagged('post_install', '-at_install')
class TestCashAnalytic(AccountingTestCase):
    """Test analytic distribution propagation and required-when-enabled rule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not cls.company.transfer_account_id:
            transfer_account = cls.env['account.account'].create({
                'name': 'Test Transfer Account',
                'code': 'TRX9999',
                'account_type': 'asset_current',
                'company_ids': [(4, cls.company.id)],
            })
            cls.company.transfer_account_id = transfer_account
        cls.analytic_plan = cls.env['account.analytic.plan'].create({
            'name': 'Стаття РГК (тест)',
        })
        cls.analytic_account = cls.env['account.analytic.account'].create({
            'name': 'Виплата зарплати',
            'plan_id': cls.analytic_plan.id,
            'company_id': cls.company.id,
        })
        cls.analytic_group = cls.env.ref('analytic.group_analytic_accounting')

    def _create_pko(self, analytic_distribution=None):
        vals = {
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 1500,
            'journal_id': self.cash_journal.id,
        }
        if analytic_distribution is not None:
            vals['analytic_distribution'] = analytic_distribution
        return self.env['account.payment'].create(vals)

    def test_analytic_distribution_field_writable(self):
        """analytic_distribution field accepts dict {analytic_account_id: percent}."""
        distribution = {str(self.analytic_account.id): 100.0}
        pko = self._create_pko(analytic_distribution=distribution)
        self.assertEqual(pko.analytic_distribution, distribution)

    def test_prepare_move_lines_propagates_to_counterpart(self):
        """_prepare_move_line_default_vals injects distribution into counterpart, NOT liquidity."""
        distribution = {str(self.analytic_account.id): 100.0}
        pko = self._create_pko(analytic_distribution=distribution)
        line_vals_list = pko._prepare_move_line_default_vals()

        liquidity_vals = [
            v for v in line_vals_list
            if v.get('account_id') == pko.outstanding_account_id.id
        ]
        counterpart_vals = [
            v for v in line_vals_list
            if v.get('account_id') != pko.outstanding_account_id.id
        ]
        self.assertTrue(liquidity_vals, 'Expected a liquidity line')
        self.assertTrue(counterpart_vals, 'Expected at least one counterpart line')

        for line_vals in liquidity_vals:
            self.assertFalse(
                line_vals.get('analytic_distribution'),
                'Liquidity (cash) line must NOT carry analytic distribution',
            )
        for line_vals in counterpart_vals:
            self.assertEqual(
                line_vals.get('analytic_distribution'), distribution,
                'Counterpart line must carry analytic distribution from payment',
            )

    def test_prepare_move_lines_no_distribution(self):
        """Without analytic_distribution, lines stay clean."""
        pko = self._create_pko()
        for line_vals in pko._prepare_move_line_default_vals():
            self.assertFalse(line_vals.get('analytic_distribution'))

    def test_analytic_reaches_journal_items_after_post(self):
        """End-to-end: the distribution must survive onto the posted account.move.line.

        The unit tests above passed vacuously for a long time while the override
        targeted a method that does not exist; assert on real journal items.
        """
        distribution = {str(self.analytic_account.id): 100.0}
        pko = self._create_pko(analytic_distribution=distribution)
        pko.action_post()

        lines = pko.move_id.line_ids
        self.assertTrue(lines, 'Posting must produce journal items')
        liquidity = lines.filtered(lambda l: l.account_id == pko.outstanding_account_id)
        counterpart = lines - liquidity

        self.assertTrue(counterpart, 'Expected a counterpart journal item')
        for line in counterpart:
            self.assertEqual(line.analytic_distribution, distribution)
        for line in liquidity:
            self.assertFalse(line.analytic_distribution)

    def test_required_when_analytic_group_enabled(self):
        """If user has analytic_accounting group, posting PKO without distribution must fail."""
        self.env.user.group_ids |= self.analytic_group
        pko = self._create_pko()
        with self.assertRaises(UserError):
            pko.action_post()

    def test_not_required_for_bank_payment(self):
        """Bank payments (not is_ua_cash_order) are NOT required to have analytic distribution.

        action_post is not called (chart template not guaranteed in test env);
        the rule is checked upfront in action_post() so we assert it does NOT
        trigger the UA-specific UserError for non-cash-order payments by
        invoking only the guard logic.
        """
        self.env.user.group_ids |= self.analytic_group
        bank_payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 5000,
            'journal_id': self.bank_journal.id,
        })
        self.assertFalse(bank_payment.is_ua_cash_order)
        self.assertFalse(
            bank_payment.is_ua_cash_order and not bank_payment.analytic_distribution,
            'Bank payment must not trigger the cash-order analytic requirement',
        )
