"""Tests for Ukrainian cash orders (PKO/VKO) — Flow 4 from ACCOUNTING_UKRAINE.md.

Tests cover:
- PKO/VKO creation and auto-sequencing
- Cash order type detection
- Cash book wizard data generation
"""

from odoo.tests import tagged
from .common import AccountingTestCase


@tagged('post_install', '-at_install')
class TestCashOrders(AccountingTestCase):
    """Test PKO/VKO cash orders (Прибуткові/Видаткові касові ордери)."""

    def test_pko_creation_auto_sequence(self):
        """PKO should get auto-generated cash order number from journal sequence."""
        payment = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 5000,
            'journal_id': self.cash_journal.id,
        })
        self.assertTrue(payment.ua_cash_order_number, 'PKO should have auto-generated number')
        self.assertTrue(payment.ua_cash_order_number.startswith('ПКО-'),
                        f'PKO number should start with ПКО-, got {payment.ua_cash_order_number}')

    def test_vko_creation_auto_sequence(self):
        """VKO should get auto-generated cash order number from journal sequence."""
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 3000,
            'journal_id': self.cash_journal.id,
        })
        self.assertTrue(payment.ua_cash_order_number, 'VKO should have auto-generated number')
        self.assertTrue(payment.ua_cash_order_number.startswith('ВКО-'),
                        f'VKO number should start with ВКО-, got {payment.ua_cash_order_number}')

    def test_cash_order_type_computed(self):
        """Cash order type should be computed based on journal type and payment direction."""
        pko = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 1000,
            'journal_id': self.cash_journal.id,
        })
        self.assertEqual(pko.ua_cash_order_type, 'pko')
        self.assertTrue(pko.is_ua_cash_order)

        vko = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 1000,
            'journal_id': self.cash_journal.id,
        })
        self.assertEqual(vko.ua_cash_order_type, 'vko')
        self.assertTrue(vko.is_ua_cash_order)

    def test_bank_payment_not_cash_order(self):
        """Bank payments should not be marked as cash orders."""
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 10000,
            'journal_id': self.bank_journal.id,
        })
        self.assertFalse(payment.is_ua_cash_order)
        self.assertEqual(payment.ua_cash_order_type, 'other')

    def test_payment_order_auto_sequence(self):
        """Bank outbound payment should get payment order number."""
        payment = self.env['account.payment'].create({
            'payment_type': 'outbound',
            'partner_type': 'supplier',
            'partner_id': self.partner.id,
            'amount': 25000,
            'journal_id': self.bank_journal.id,
        })
        self.assertTrue(payment.ua_payment_order_number,
                        'Payment order should have auto-generated number')
        self.assertTrue(payment.ua_payment_order_number.startswith('ПД-'),
                        f'PD number should start with ПД-, got {payment.ua_payment_order_number}')
        self.assertTrue(payment.is_ua_payment_order)
        self.assertEqual(payment.ua_payment_order_type, 'pd')

    def test_sequence_increment(self):
        """Each new cash order should get an incremented number."""
        pko1 = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 1000,
            'journal_id': self.cash_journal.id,
        })
        pko2 = self.env['account.payment'].create({
            'payment_type': 'inbound',
            'partner_type': 'customer',
            'partner_id': self.partner.id,
            'amount': 2000,
            'journal_id': self.cash_journal.id,
        })
        self.assertNotEqual(pko1.ua_cash_order_number, pko2.ua_cash_order_number,
                            'Each PKO should have a unique number')

    def test_cash_book_wizard_creation(self):
        """Cash book wizard should accept date range and journal."""
        from datetime import date
        wizard = self.env['l10n_ua.cash.book.wizard'].create({
            'journal_id': self.cash_journal.id,
            'date_from': date(2025, 1, 1),
            'date_to': date(2025, 12, 31),
        })
        self.assertTrue(wizard)
        # Should be able to get report data without errors
        data = wizard._get_cash_book_data()
        self.assertIsInstance(data, dict)

    def test_journal_sequences_created(self):
        """Cash journal should have PKO and VKO sequences after creation."""
        self.assertTrue(self.cash_journal.ua_pko_sequence_id,
                        'Cash journal should have PKO sequence')
        self.assertTrue(self.cash_journal.ua_vko_sequence_id,
                        'Cash journal should have VKO sequence')

    def test_bank_journal_pd_sequence(self):
        """Bank journal should have PD sequence after creation."""
        self.assertTrue(self.bank_journal.ua_pd_sequence_id,
                        'Bank journal should have PD sequence')
