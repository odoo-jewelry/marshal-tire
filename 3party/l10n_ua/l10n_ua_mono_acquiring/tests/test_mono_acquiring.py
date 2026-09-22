"""Monobank Acquiring — логіка кошика/журналу (без мережі)."""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestMonoAcquiring(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({'name': 'Клієнт'})
        cls.product = cls.env['product.product'].create({
            'name': 'Товар', 'list_price': 100.0, 'default_code': 'P1'})
        cls.journal = cls.env['account.journal'].create({
            'name': 'Mono', 'type': 'bank', 'code': 'MONO',
            'company_id': cls.company.id,
            'mono_acquiring_token': 'test-token'})

    def _sale(self):
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'product_uom_qty': 2, 'price_unit': 100.0})]})

    def _invoice(self):
        return self.env['account.move'].create({
            'move_type': 'out_invoice', 'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 3, 'price_unit': 100.0})]})

    # --- Журнал з токеном ---

    def test_journal_resolved(self):
        so = self._sale()
        self.assertEqual(so._get_mono_acquiring_journal(), self.journal)

    def test_journal_missing_raises(self):
        self.journal.mono_acquiring_token = False
        so = self._sale()
        with self.assertRaises(UserError):
            so._get_mono_acquiring_journal()

    # --- Кошик / сума ---

    def test_sale_basket_and_amount(self):
        so = self._sale()
        self.assertAlmostEqual(so._mono_amount(), so.amount_total, places=2)
        basket = so._mono_basket()
        self.assertEqual(len(basket), 1)
        line = basket[0]
        self.assertEqual(line['qty'], 2)
        # sum — ціна за одиницю в копійках (200 subtotal / 2 = 100.00 → 10000)
        self.assertEqual(line['sum'], 10000)
        self.assertEqual(line['code'], 'P1')

    def test_invoice_basket_and_amount(self):
        inv = self._invoice()
        self.assertAlmostEqual(inv._mono_amount(), inv.amount_residual, places=2)
        basket = inv._mono_basket()
        self.assertEqual(len(basket), 1)
        self.assertEqual(basket[0]['qty'], 3)
        self.assertEqual(basket[0]['sum'], 10000)

    def test_invoice_wrong_type_blocked(self):
        bill = self.env['account.move'].create({
            'move_type': 'in_invoice', 'partner_id': self.partner.id})
        with self.assertRaises(UserError):
            bill.action_create_mono_link()

    def test_sale_write_clears_link(self):
        so = self._sale()
        so.mono_payment_link = 'https://x'
        so.mono_invoice_id = 'inv1'
        so.write({'order_line': [(0, 0, {
            'product_id': self.product.id, 'product_uom_qty': 1,
            'price_unit': 50.0})]})
        self.assertFalse(so.mono_payment_link)
        self.assertFalse(so.mono_invoice_id)
