"""Tests for PRRO receipt total_amount — issue #186.

`total_amount` is a stored computed field (cash + card). The Checkbox
integration used to write `total_amount` directly in the create vals, where the
compute immediately overwrote it to 0 (cash/card unset), losing the API total.
The fix maps the payments split into cash/card so the total is real, and lets
the compute fall back to the goods subtotal.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReceiptTotal(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['l10n_ua.prro.config'].create({
            'name': 'Каса (тест)',
            'provider': 'checkbox',
            'company_id': cls.env.company.id,
        })
        cls.shift = cls.env['l10n_ua.prro.shift'].create({
            'config_id': cls.config.id,
        })
        cls.Receipt = cls.env['l10n_ua.prro.receipt']

    def _receipt(self, **vals):
        vals.setdefault('shift_id', self.shift.id)
        return self.Receipt.create(vals)

    # --- _prepare_payment_vals ---

    def test_payment_vals_cash_only(self):
        vals = self.Receipt._prepare_payment_vals([{'type': 'CASH', 'value': 15000}])
        self.assertEqual(vals['cash_amount'], 150.0)
        self.assertEqual(vals['card_amount'], 0.0)
        self.assertEqual(vals['payment_type'], 'cash')

    def test_payment_vals_card_only(self):
        vals = self.Receipt._prepare_payment_vals([{'type': 'CASHLESS', 'value': 20000}])
        self.assertEqual(vals['cash_amount'], 0.0)
        self.assertEqual(vals['card_amount'], 200.0)
        self.assertEqual(vals['payment_type'], 'card')

    def test_payment_vals_mixed(self):
        vals = self.Receipt._prepare_payment_vals([
            {'type': 'CASH', 'value': 5000},
            {'type': 'CASHLESS', 'value': 7000},
        ])
        self.assertEqual(vals['cash_amount'], 50.0)
        self.assertEqual(vals['card_amount'], 70.0)
        self.assertEqual(vals['payment_type'], 'mixed')

    def test_payment_vals_empty(self):
        vals = self.Receipt._prepare_payment_vals([])
        self.assertEqual(vals['cash_amount'], 0.0)
        self.assertEqual(vals['card_amount'], 0.0)

    # --- total_amount compute ---

    def test_total_from_payments(self):
        receipt = self._receipt(cash_amount=100.0, card_amount=50.0)
        self.assertEqual(receipt.total_amount, 150.0)

    def test_total_falls_back_to_lines(self):
        """No payment split -> total taken from goods subtotal (not 0)."""
        receipt = self._receipt(line_ids=[
            (0, 0, {'name': 'Товар А', 'quantity': 2, 'price_unit': 30.0}),
            (0, 0, {'name': 'Товар Б', 'quantity': 1, 'price_unit': 40.0}),
        ])
        self.assertEqual(receipt.total_amount, 100.0)

    def test_regression_checkbox_receipt_total_not_zero(self):
        """Receipt built the way the Checkbox flow does it has a real total."""
        vals = {
            'shift_id': self.shift.id,
            'fiscal_number': 'FC-1',
            'receipt_type': 'sale',
            'state': 'registered',
        }
        vals.update(self.Receipt._prepare_payment_vals(
            [{'type': 'CASH', 'value': 12300}]))
        receipt = self.Receipt.create(vals)
        self.assertEqual(receipt.total_amount, 123.0)
        self.assertNotEqual(receipt.total_amount, 0.0)
