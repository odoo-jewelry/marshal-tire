from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionEditing(PosOrderCorrectionCommon):
    def test_prepare_cancel_and_apply_price_change(self):
        order = self._create_paid_order("correction-edit-1")
        original_date = order.date_order
        original_session = order.session_id
        correction = self._prepare(order)

        self.assertEqual(correction.state, "draft")
        self.assertFalse(correction.applied_order_id)
        self.assertEqual(correction.line_ids.product_id, self.product100)
        self.assertEqual(correction.payment_ids.amount, 100)

        correction.action_cancel()
        self.assertEqual(correction.state, "cancelled")
        self.assertFalse(correction.applied_order_id)

        correction = self._prepare(order)

        correction.line_ids.price_unit = 120
        correction.payment_ids.amount = 120
        correction.reason = "Wrong product price"
        correction.action_apply()

        difference_order = correction.applied_order_id
        self.assertEqual(correction.state, "applied")
        self.assertEqual(difference_order.state, "paid")
        self.assertEqual(difference_order.correction_root_id, order)
        self.assertEqual(difference_order.amount_total, 20)
        self.assertEqual(difference_order.amount_paid, 20)
        self.assertEqual(len(difference_order.lines), 2)
        self.assertTrue(difference_order.lines.filtered("refunded_orderline_id"))
        self.assertEqual(sum(difference_order.lines.mapped("correction_stock_qty")), 0)
        self.assertFalse(difference_order.picking_ids)
        self.assertEqual(order.date_order, original_date)
        self.assertEqual(order.session_id, original_session)
        self.assertEqual(order.lines.price_unit, 100)
        self.assertTrue(correction.before_snapshot)
        self.assertTrue(correction.after_snapshot)
        self.assertTrue(correction.pending_processing)
        self.assertEqual(order.correction_current_line_ids, difference_order.lines.filtered(
            lambda line: line.qty > 0
        ))
        self.assertEqual(order.correction_current_total, 120)
        self.assertIn("120", order.correction_current_payments)
        self.assertEqual(order.correction_count, 2)
        self.assertFalse(order.correction_stock_pending)
        self.assertEqual(order.action_open_correction_history()["domain"], [
            ("root_order_id", "=", order.id)
        ])

    def test_reason_and_noop_are_rejected(self):
        order = self._create_paid_order("correction-edit-2")
        correction = self._prepare(order)
        correction.reason = " "
        with self.assertRaises(ValidationError):
            correction.action_apply()
        correction.reason = "No actual change"
        with self.assertRaises(UserError):
            correction.action_apply()

    def test_second_revision_uses_current_projection(self):
        order = self._create_paid_order("correction-edit-3")
        first = self._prepare(order)
        first.line_ids.product_id = self.product80
        first.line_ids.price_unit = 80
        first.payment_ids.amount = 80
        first.reason = "Product B was sold"
        first.action_apply()

        second = self._prepare(order)
        self.assertEqual(second.base_revision, first.revision)
        self.assertEqual(second.line_ids.product_id, self.product80)
        second.line_ids.product_id = self.product100
        second.line_ids.price_unit = 100
        second.payment_ids.amount = 100
        second.reason = "Product C was sold"
        second.action_apply()

        self.assertEqual(second.revision, first.revision + 1)
        self.assertEqual(order._get_effective_correction_lines().product_id, self.product100)
        self.assertEqual(order._get_effective_correction_lines().order_id, second.applied_order_id)
        self.assertEqual(order.lines.product_id, self.product100)

    def test_unchanged_product_is_not_offset(self):
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders([{
            "pos_order_lines_ui_args": [(self.product100, 1), (self.product80, 1)],
            "payments": [(self.cash_pm1, 180)],
            "customer": self.customer, "uuid": "correction-unchanged-line",
        }])["correction-unchanged-line"]
        original_line = order.lines.filtered(lambda line: line.product_id == self.product80)
        correction = self._prepare(order)
        correction.line_ids.filtered(lambda line: line.product_id == self.product100).price_unit = 120
        correction.payment_ids.amount = 200
        correction.reason = "Correct one item price"
        correction.action_apply()
        self.assertNotIn(self.product80, correction.applied_order_id.lines.product_id)
        self.assertIn(original_line, order._get_effective_correction_lines())
        self.assertFalse(correction.applied_order_id.picking_ids)

    def test_draft_cancelled_and_return_orders_are_ineligible(self):
        order = self._create_paid_order("correction-ineligible-types")
        for state in ("draft", "cancel"):
            with self.subTest(state=state):
                source = order.copy({"state": state})
                with self.assertRaises(UserError):
                    source.action_prepare_correction()
                self.assertFalse(source.correction_ids)
        refund = order._refund()
        with self.assertRaises(UserError):
            refund.action_prepare_correction()
        self.assertFalse(refund.correction_ids)

    def test_empty_sale_can_be_restored_by_a_new_revision(self):
        order = self._create_paid_order("correction-empty-sale")
        correction = self._prepare(order)
        correction.line_ids.unlink()
        correction.payment_ids.unlink()
        correction.reason = "No products were sold"
        correction.action_apply()
        self.assertFalse(order._get_effective_correction_lines())
        self.assertEqual(correction.applied_order_id.amount_total, -100)

        restored = self._prepare(order)
        self.assertFalse(restored.line_ids)
        self.assertFalse(restored.payment_ids)
        restored.write({
            "line_ids": [Command.create({
                "product_id": self.product100.id, "qty": 1, "price_unit": 100,
            })],
            "payment_ids": [Command.create({
                "payment_method_id": self.cash_pm1.id, "amount": 100,
            })],
            "reason": "Restore the sale by another revision",
        })
        restored.action_apply()
        self.assertEqual(restored.applied_order_id.amount_total, 100)
        self.assertEqual(restored.applied_order_id.amount_paid, 100)
        self.assertEqual(order.correction_current_total, 100)
