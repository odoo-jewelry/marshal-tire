from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PosCustomerDebtCommon


@tagged("post_install", "-at_install")
class TestPosCustomerDebtSources(PosCustomerDebtCommon):
    def test_ordinary_cash_sale_keeps_standard_accounting_and_stock_flow(self):
        session, orders = self._close_orders(
            [
                {
                    "pos_order_lines_ui_args": [(self.product100, 1)],
                    "payments": [(self.cash_pm1, 100)],
                    "customer": self.customer,
                    "is_invoiced": False,
                    "uuid": "ordinary-cash-sale",
                }
            ]
        )
        order = orders["ordinary-cash-sale"]

        self.assertEqual(order.debt_state, "not_applicable")
        self.assertFalse(order.debt_source_line_ids)
        self.assertEqual(session.move_id.state, "posted")
        self.assertEqual(sum(session.move_id.line_ids.mapped("balance")), 0)
        self.assertTrue(order.picking_ids)
        self.assertEqual(set(order.picking_ids.mapped("state")), {"done"})

    def test_closed_session_mixed_payment_creates_order_debt(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-source-1", cash=30, debt=70)]
        )
        order = orders["debt-source-1"]

        self.assertEqual(order.debt_state, "outstanding")
        self.assertEqual(order.debt_original_amount, 70)
        self.assertEqual(order.debt_residual_amount, 70)
        self.assertEqual(len(order.debt_source_line_ids), 1)
        self.assertEqual(
            order.debt_source_line_ids.pos_debt_payment_id.payment_method_id.type,
            "pay_later",
        )
        self.assertIn(
            order,
            self.env["pos.order"].search([("debt_state", "=", "outstanding")]),
        )

    def test_open_session_debt_cannot_be_settled(self):
        self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        orders = self._create_orders(
            [self._pay_later_order_values("debt-source-open")]
        )
        order = orders["debt-source-open"]

        self.assertEqual(order.debt_state, "pending_session")
        with self.assertRaises(UserError):
            order.action_register_debt_payment()

    def test_open_session_invoiced_debt_cannot_be_settled(self):
        self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        orders = self._create_orders(
            [
                self._pay_later_order_values(
                    "debt-source-open-invoiced", is_invoiced=True
                )
            ]
        )
        order = orders["debt-source-open-invoiced"]

        self.assertTrue(order.account_move)
        self.assertEqual(order.debt_state, "pending_session")
        with self.assertRaises(UserError):
            order.action_register_debt_payment()

    def test_invoiced_order_uses_invoice_as_single_source(self):
        _session, orders = self._close_orders(
            [
                self._pay_later_order_values(
                    "debt-source-invoiced", cash=30, debt=70, is_invoiced=True
                )
            ]
        )
        order = orders["debt-source-invoiced"]

        self.assertEqual(order.debt_original_amount, 70)
        self.assertEqual(order.debt_residual_amount, 70)
        self.assertEqual(order.debt_source_line_ids.move_id, order.account_move)
        self.assertFalse(order.payment_ids.debt_move_line_ids)

    def test_renamed_customer_account_method_remains_identified(self):
        self.pay_later_pm.name = "Client Ledger"
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-source-name")]
        )
        self.assertEqual(orders["debt-source-name"].debt_state, "outstanding")

    def test_standard_accounting_reconciliation_updates_debt(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-source-reconcile")]
        )
        order = orders["debt-source-reconcile"]
        payment = self._create_incoming_payment(40)
        payment.action_post()

        (order.debt_source_line_ids | payment._get_pos_debt_counterpart_lines()).reconcile()

        self.assertEqual(order.debt_residual_amount, 60)
        self.assertEqual(order.debt_payment_amount, 40)
        partials = order.debt_source_line_ids.matched_credit_ids
        partials.unlink()
        self.assertEqual(order.debt_residual_amount, 100)
        self.assertEqual(order.debt_payment_amount, 0)
