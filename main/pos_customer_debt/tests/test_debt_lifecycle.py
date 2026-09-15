from odoo import Command
from odoo.tests import tagged

from .common import PosCustomerDebtCommon


@tagged("post_install", "-at_install")
class TestPosCustomerDebtLifecycle(PosCustomerDebtCommon):
    def test_invoice_after_partial_settlement_keeps_each_order_balance(self):
        _session, orders = self._close_orders(
            [
                self._pay_later_order_values("debt-invoice-1"),
                self._pay_later_order_values("debt-invoice-2"),
            ]
        )
        order1 = orders["debt-invoice-1"]
        order2 = orders["debt-invoice-2"]
        payment = self._create_incoming_payment(40)
        self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": order1.id, "amount": 40}
        )
        payment.action_post()

        order1.with_context(generate_pdf=False).action_pos_order_invoice()

        self.assertEqual(order1.debt_residual_amount, 60)
        self.assertEqual(order2.debt_residual_amount, 100)
        self.assertEqual(order1.account_move.amount_residual, 60)
        self.assertEqual(order1.debt_payment_amount, 40)

    def test_late_invoice_with_multiple_payment_terms_keeps_residual(self):
        payment_term = self.env["account.payment.term"].create(
            {
                "name": "Two POS Debt Installments",
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 50, "nb_days": 0}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 50, "nb_days": 30}
                    ),
                ],
            }
        )
        self.customer.property_payment_term_id = payment_term
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-invoice-installments")]
        )
        order = orders["debt-invoice-installments"]
        payment = self._create_incoming_payment(40)
        self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": order.id, "amount": 40}
        )
        payment.action_post()

        order.with_context(generate_pdf=False).action_pos_order_invoice()

        receivable_lines = order.account_move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        self.assertEqual(len(receivable_lines), 2)
        self.assertEqual(sum(receivable_lines.mapped("amount_residual_currency")), 60)
        self.assertEqual(order.debt_residual_amount, 60)

    def test_customer_account_refund_offsets_only_source_debt(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-refund-source")]
        )
        order = orders["debt-refund-source"]
        refund_session = self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        refund_values = self.create_ui_order_data(
            [
                {
                    "product": self.product100,
                    "quantity": -0.3,
                    "refunded_orderline_id": order.lines.id,
                }
            ],
            customer=self.customer,
            payments=[(self.pay_later_pm, -30)],
            uuid="debt-refund-credit",
        )
        self.env["pos.order"].sync_from_ui([refund_values])
        refund_session.post_closing_cash_details(0)
        refund_session.close_session_from_ui()

        self.assertEqual(order.debt_residual_amount, 70)
        self.assertEqual(order.debt_adjustment_amount, 30)

    def test_cash_refund_does_not_offset_debt(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-refund-cash-source")]
        )
        order = orders["debt-refund-cash-source"]
        refund_session = self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        refund_values = self.create_ui_order_data(
            [
                {
                    "product": self.product100,
                    "quantity": -0.3,
                    "refunded_orderline_id": order.lines.id,
                }
            ],
            customer=self.customer,
            payments=[(self.cash_pm1, -30)],
            uuid="debt-refund-cash",
        )
        self.env["pos.order"].sync_from_ui([refund_values])
        refund_session.post_closing_cash_details(-30)
        refund_session.close_session_from_ui()

        self.assertEqual(order.debt_residual_amount, 100)

    def test_refund_excess_remains_customer_credit(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-refund-excess-source")]
        )
        order = orders["debt-refund-excess-source"]
        payment = self._create_incoming_payment(80)
        self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": order.id, "amount": 80}
        )
        payment.action_post()
        refund_session = self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        refund_values = self.create_ui_order_data(
            [
                {
                    "product": self.product100,
                    "quantity": -0.5,
                    "refunded_orderline_id": order.lines.id,
                }
            ],
            customer=self.customer,
            payments=[(self.pay_later_pm, -50)],
            uuid="debt-refund-excess-credit",
        )
        self.env["pos.order"].sync_from_ui([refund_values])
        refund_session.post_closing_cash_details(0)
        refund_session.close_session_from_ui()

        credit_lines = refund_session.order_ids.payment_ids.debt_move_line_ids.filtered(
            lambda line: line.amount_residual_currency < 0
        )
        self.assertEqual(order.debt_residual_amount, 0)
        self.assertEqual(order.debt_adjustment_amount, 20)
        self.assertEqual(sum(credit_lines.mapped("amount_residual_currency")), -30)

    def test_open_customer_account_refund_does_not_offset_debt(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-refund-open-source")]
        )
        order = orders["debt-refund-open-source"]
        self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        refund_values = self.create_ui_order_data(
            [
                {
                    "product": self.product100,
                    "quantity": -0.3,
                    "refunded_orderline_id": order.lines.id,
                }
            ],
            customer=self.customer,
            payments=[(self.pay_later_pm, -30)],
            uuid="debt-refund-open-credit",
        )
        self.env["pos.order"].sync_from_ui([refund_values])

        self.assertEqual(order.debt_residual_amount, 100)

    def test_ambiguous_customer_account_refund_is_not_applied(self):
        _session, orders = self._close_orders(
            [
                self._pay_later_order_values("debt-refund-ambiguous-source-1"),
                self._pay_later_order_values("debt-refund-ambiguous-source-2"),
            ]
        )
        order1 = orders["debt-refund-ambiguous-source-1"]
        order2 = orders["debt-refund-ambiguous-source-2"]
        refund_session = self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        refund_values = self.create_ui_order_data(
            [(self.product100, -0.3)],
            customer=self.customer,
            payments=[(self.pay_later_pm, -30)],
            uuid="debt-refund-ambiguous-credit",
        )
        self.env["pos.order"].sync_from_ui([refund_values])
        refund_session.post_closing_cash_details(0)
        refund_session.close_session_from_ui()

        self.assertEqual(order1.debt_residual_amount, 100)
        self.assertEqual(order2.debt_residual_amount, 100)
        self.assertTrue(
            refund_session.order_ids.filtered(
                lambda order: order.uuid == "debt-refund-ambiguous-credit"
            ).debt_review_reason
        )

    def test_removed_refund_reconciliation_is_not_reapplied(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-refund-unreconcile-source")]
        )
        order = orders["debt-refund-unreconcile-source"]
        refund_session = self._start_pos_session(self.cash_pm1 | self.pay_later_pm, 0)
        refund_values = self.create_ui_order_data(
            [
                {
                    "product": self.product100,
                    "quantity": -0.3,
                    "refunded_orderline_id": order.lines.id,
                }
            ],
            customer=self.customer,
            payments=[(self.pay_later_pm, -30)],
            uuid="debt-refund-unreconcile-credit",
        )
        self.env["pos.order"].sync_from_ui([refund_values])
        refund_session.post_closing_cash_details(0)
        refund_session.close_session_from_ui()
        refund_partials = order.debt_source_line_ids.matched_credit_ids

        refund_partials.unlink()

        self.assertEqual(order.debt_residual_amount, 100)
