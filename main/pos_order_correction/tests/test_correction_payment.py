from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionPayment(PosOrderCorrectionCommon):
    def test_cash_to_bank_creates_zero_product_order(self):
        order = self._create_paid_order("correction-payment-1", self.cash_pm1)
        correction = self._prepare(order)
        correction.payment_ids.payment_method_id = self.bank_pm1
        correction.reason = "Wrong payment method"
        correction.action_apply()

        difference_order = correction.applied_order_id
        self.assertFalse(difference_order.lines)
        self.assertEqual(difference_order.amount_total, 0)
        self.assertEqual(difference_order.amount_paid, 0)
        self.assertEqual(
            {
                payment.payment_method_id.id: payment.amount
                for payment in difference_order.payment_ids
            },
            {self.cash_pm1.id: -100, self.bank_pm1.id: 100},
        )

    def test_split_payment_records_only_method_differences(self):
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders(
            [
                {
                    "pos_order_lines_ui_args": [(self.product100, 1)],
                    "payments": [(self.cash_pm1, 70), (self.bank_pm1, 30)],
                    "customer": self.customer,
                    "is_invoiced": False,
                    "uuid": "correction-payment-2",
                }
            ]
        )["correction-payment-2"]
        correction = self._prepare(order)
        correction.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.cash_pm1
        ).amount = 20
        correction.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.bank_pm1
        ).amount = 80
        correction.reason = "Wrong split payment"
        correction.action_apply()

        self.assertEqual(
            {
                payment.payment_method_id.id: payment.amount
                for payment in correction.applied_order_id.payment_ids
            },
            {self.cash_pm1.id: -50, self.bank_pm1.id: 50},
        )
        self.assertFalse(correction.applied_order_id.lines)

    def test_bank_to_cash_preserves_original_payment_evidence(self):
        order = self._create_paid_order("correction-payment-bank", self.bank_pm1)
        order.payment_ids.write({"transaction_id": "recorded-reference", "payment_status": "done"})
        picking_ids = order.picking_ids.ids
        correction = self._prepare(order)
        correction.payment_ids.payment_method_id = self.cash_pm1
        correction.reason = "Correct payment registration"
        correction.action_apply()

        self.assertEqual(order.payment_ids.transaction_id, "recorded-reference")
        self.assertEqual(order.payment_ids.payment_status, "done")
        self.assertFalse(any(correction.applied_order_id.payment_ids.mapped("transaction_id")))
        self.assertFalse(correction.applied_order_id.picking_ids)
        self.assertEqual(order.picking_ids.ids, picking_ids)
        self.assertEqual(correction.applied_order_id.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.cash_pm1
        ).amount, 100)

    def test_unmatched_total_rolls_back_all_documents(self):
        order = self._create_paid_order("correction-payment-insufficient")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 120
        correction.reason = "Missing allocation"
        before = self.env["pos.order"].search_count([])
        with self.assertRaises(UserError):
            correction.action_apply()
        self.assertEqual(self.env["pos.order"].search_count([]), before)
        self.assertEqual(correction.state, "draft")
        self.assertFalse(correction.applied_order_id)

    def test_terminal_registration_change_is_rejected(self):
        with patch.object(type(self.bank_pm1), "_get_payment_terminal_selection",
                          return_value=[("test_terminal", "Test Terminal")]):
            self.bank_pm1.use_payment_terminal = "test_terminal"
            order = self._create_paid_order("correction-payment-terminal", self.bank_pm1)
            correction = self._prepare(order)
            correction.payment_ids.payment_method_id = self.cash_pm1
            correction.reason = "A terminal reversal would be required"
            with self.assertRaises(UserError):
                correction.action_apply()
            self.assertFalse(correction.applied_order_id)
            self.assertEqual(order.payment_ids.amount, 100)

    def test_tax_inclusive_price_and_product_replacement(self):
        tax = self.env["account.tax"].create({
            "name": "Included correction tax", "amount": 20,
            "amount_type": "percent", "price_include_override": "tax_included",
            "company_id": self.env.company.id,
        })
        self.product80.taxes_id = [Command.set(tax.ids)]
        order = self._create_paid_order("correction-payment-tax")
        correction = self._prepare(order)
        correction.line_ids.write({"product_id": self.product80.id, "price_unit": 120})
        correction.payment_ids.amount = 120
        correction.reason = "Correct taxed product"
        correction.action_apply()

        result_line = correction.line_ids.result_order_line_id
        self.assertEqual(result_line.tax_ids, tax)
        self.assertAlmostEqual(result_line.price_subtotal, 100)
        self.assertAlmostEqual(result_line.price_subtotal_incl, 120)
        self.assertAlmostEqual(correction.applied_order_id.amount_tax, 20)
        self.assertAlmostEqual(correction.applied_order_id.amount_total, 20)

    def test_original_cash_change_is_not_repeated(self):
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders([{
            "pos_order_lines_ui_args": [(self.product100, 1)],
            "payments": [(self.cash_pm1, 120)],
            "pos_order_ui_args": {"amount_return": -20},
            "customer": self.customer,
            "uuid": "correction-payment-change",
        }])["correction-payment-change"]
        correction = self._prepare(order)
        self.assertEqual(correction.payment_ids.amount, 100)
        correction.payment_ids.payment_method_id = self.bank_pm1
        correction.reason = "Wrong method with cash change"
        correction.action_apply()
        self.assertEqual(sum(order.payment_ids.mapped("amount")), 100)
        self.assertEqual(correction.applied_order_id.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.cash_pm1
        ).amount, -100)
        self.assertFalse(correction.applied_order_id.payment_ids.filtered("is_change"))

    def test_replacement_applies_fiscal_position_once(self):
        taxes = self.env["account.tax"].create([
            {"name": name, "amount": amount, "company_id": self.env.company.id}
            for name, amount in (("Source 20", 20), ("Mapped 10", 10), ("Other 5", 5))
        ])
        taxes[1].original_tax_ids = [Command.set(taxes[0].ids)]
        taxes[2].original_tax_ids = [Command.set(taxes[1].ids)]
        position = self.env["account.fiscal.position"].create({
            "name": "Correction fiscal position", "company_id": self.env.company.id,
            "tax_ids": [Command.set(taxes[1:].ids)],
        })
        self.assertEqual(position.map_tax(taxes[0]), taxes[1])
        self.customer.property_account_position_id = position
        self.product80.taxes_id = [Command.set(taxes[0].ids)]
        order = self._create_paid_order("correction-payment-fiscal")
        self.assertEqual(order.fiscal_position_id, position)
        correction = self._prepare(order)
        correction.line_ids.write({"product_id": self.product80.id, "price_unit": 100})
        correction.payment_ids.amount = 110
        correction.reason = "Use the product tax and the original fiscal position"
        correction.action_apply()
        line = correction.line_ids.result_order_line_id
        self.assertEqual(line.tax_ids, taxes[0])
        self.assertEqual(line.tax_ids_after_fiscal_position, taxes[1])
        self.assertAlmostEqual(line.price_subtotal_incl, 110)

    def test_cash_rounding_validates_full_desired_distribution(self):
        self.config.write({
            "cash_rounding": True,
            "only_round_cash_method": True,
            "rounding_method": self.env["account.cash.rounding"].create({
                "name": "Correction rounding", "rounding": 0.05,
                "strategy": "add_invoice_line", "rounding_method": "HALF-UP",
                "profit_account_id": self.company.default_cash_difference_income_account_id.id,
                "loss_account_id": self.company.default_cash_difference_expense_account_id.id,
            }).id,
        })
        order = self._create_paid_order("correction-payment-rounding")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 100.03
        correction.payment_ids.amount = 100.05
        correction.reason = "Rounded corrected price"
        correction.action_apply()
        self.assertAlmostEqual(correction.applied_order_id.amount_total, 0.03)
        self.assertAlmostEqual(correction.applied_order_id.amount_paid, 0.05)
        self.assertFalse(correction.applied_order_id.picking_ids)

    def test_closed_session_payment_change_posts_cash_and_bank_difference(self):
        order = self._create_paid_order("correction-payment-closed")
        self._close_session(self.session)
        old_session = self.session
        old_accounting = old_session.move_id.line_ids.read(["debit", "credit", "account_id"])
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        correction = self._prepare(order)
        correction.payment_ids.payment_method_id = self.bank_pm1
        correction.reason = "Correct payment registration after closing"
        correction.action_apply()
        self._close_session(self.session)

        self.assertEqual(self.session.state, "closed")
        self.assertEqual(sum(self.session.statement_line_ids.mapped("amount")), -100)
        self.assertEqual(sum(self.session.bank_payment_ids.mapped("amount")), 100)
        self.assertEqual(old_session.move_id.line_ids.read(["debit", "credit", "account_id"]), old_accounting)
        self.assertFalse(correction.pending_processing)
        self.assertFalse(correction.applied_order_id.lines)
