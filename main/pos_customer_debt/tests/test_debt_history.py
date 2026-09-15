from odoo import Command
from odoo.tests import tagged

from .common import PosCustomerDebtCommon


@tagged("post_install", "-at_install")
class TestPosCustomerDebtHistory(PosCustomerDebtCommon):
    def setUp(self):
        super().setUp()
        self.env.user.write(
            {
                "group_ids": [
                    Command.link(
                        self.env.ref(
                            "pos_customer_debt.group_pos_customer_debt_link_manager"
                        ).id
                    )
                ]
            }
        )

    def test_unique_historical_line_is_linked_idempotently(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-history-unique")]
        )
        order = orders["debt-history-unique"]
        line = order.debt_source_line_ids
        line.pos_debt_payment_id = False
        order.invalidate_recordset()
        self.assertEqual(order.debt_state, "review_required")

        wizard = self.env["pos.customer.debt.link.review"].create(
            {"order_ids": [Command.set(order.ids)]}
        )
        wizard.action_analyze()
        self.assertEqual(wizard.linked_count, 1)
        wizard.action_analyze()

        self.assertEqual(line.pos_debt_payment_id, order.payment_ids)
        self.assertEqual(wizard.linked_count, 0)
        self.assertEqual(order.debt_state, "outstanding")

    def test_equal_historical_amounts_remain_for_review(self):
        _session, orders = self._close_orders(
            [
                self._pay_later_order_values("debt-history-ambiguous-1"),
                self._pay_later_order_values("debt-history-ambiguous-2"),
            ]
        )
        selected_orders = orders["debt-history-ambiguous-1"] | orders[
            "debt-history-ambiguous-2"
        ]
        selected_orders.mapped("debt_source_line_ids").pos_debt_payment_id = False
        selected_orders.invalidate_recordset()
        wizard = self.env["pos.customer.debt.link.review"].create(
            {"order_ids": [Command.set(selected_orders.ids)]}
        )

        wizard.action_analyze()

        self.assertEqual(wizard.linked_count, 0)
        self.assertEqual(wizard.review_count, 2)
        self.assertTrue(
            all(order.debt_state == "review_required" for order in selected_orders)
        )
