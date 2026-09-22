"""UA cash-order logic must not touch companies of other countries — issues #173, #174."""

from odoo.tests import tagged
from .common import AccountingTestCase


@tagged('post_install', '-at_install')
class TestNonUaCompany(AccountingTestCase):
    """A non-Ukrainian company sharing the database gets no ПКО/ВКО/ПД treatment."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create first, set the country after: passing country_id to create()
        # makes base auto-install that country's l10n module mid-test.
        cls.foreign_company = cls.env['res.company'].create({
            'name': 'Test Bohemia s.r.o.',
        })
        cls.foreign_company.country_id = cls.env.ref('base.cz')
        cls.env.user.company_ids = [(4, cls.foreign_company.id)]
        # A payment needs a chart of accounts; any non-UA one proves the point.
        cls.env['account.chart.template'].with_company(cls.foreign_company).try_loading(
            'generic_coa', company=cls.foreign_company, install_demo=False)
        cls.foreign_cash_journal = cls.env['account.journal'].create({
            'name': 'Pokladna',
            'code': 'CSHF',
            'type': 'cash',
            'company_id': cls.foreign_company.id,
        })
        cls.foreign_bank_journal = cls.env['account.journal'].create({
            'name': 'Banka',
            'code': 'BNKF',
            'type': 'bank',
            'company_id': cls.foreign_company.id,
        })
        cls.foreign_partner = cls.env['res.partner'].create({'name': 'Zákazník Praha'})

    def _create_foreign_payment(self, payment_type='inbound', journal=None):
        return self.env['account.payment'].with_company(self.foreign_company).create({
            'payment_type': payment_type,
            'partner_type': 'customer',
            'partner_id': self.foreign_partner.id,
            'amount': 500,
            'journal_id': (journal or self.foreign_cash_journal).id,
            'company_id': self.foreign_company.id,
        })

    def test_no_ua_sequences_on_foreign_journals(self):
        """Creating journals for a foreign company must not build ПКО/ВКО/ПД sequences."""
        self.assertFalse(self.foreign_cash_journal.ua_pko_sequence_id)
        self.assertFalse(self.foreign_cash_journal.ua_vko_sequence_id)
        self.assertFalse(self.foreign_bank_journal.ua_pd_sequence_id)

    def test_ua_sequences_still_created_for_ua_company(self):
        """The Ukrainian company keeps its sequences — the guard must not over-reach."""
        self.assertTrue(self.cash_journal.ua_pko_sequence_id)
        self.assertTrue(self.cash_journal.ua_vko_sequence_id)
        self.assertTrue(self.bank_journal.ua_pd_sequence_id)

    def test_foreign_payment_is_not_a_ua_cash_order(self):
        payment = self._create_foreign_payment()
        self.assertFalse(payment.is_ua_cash_order)
        self.assertEqual(payment.ua_cash_order_type, 'other')
        self.assertFalse(payment.ua_cash_order_number)

    def test_foreign_bank_payment_is_not_a_ua_payment_order(self):
        payment = self._create_foreign_payment(
            payment_type='outbound', journal=self.foreign_bank_journal)
        self.assertFalse(payment.is_ua_payment_order)
        self.assertEqual(payment.ua_payment_order_type, 'other')
        self.assertFalse(payment.ua_payment_order_number)

    def test_foreign_cash_payment_posts_with_analytic_accounting_on(self):
        """The regression from #173: posting raised a Ukrainian UserError."""
        self.env.user.group_ids = [
            (4, self.env.ref('analytic.group_analytic_accounting').id)]
        payment = self._create_foreign_payment()
        payment.action_post()
        self.assertNotEqual(payment.state, 'draft')
