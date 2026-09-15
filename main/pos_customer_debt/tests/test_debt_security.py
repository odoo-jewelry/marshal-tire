from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import PosCustomerDebtCommon


@tagged("post_install", "-at_install")
class TestPosCustomerDebtSecurity(PosCustomerDebtCommon):
    def test_viewer_cannot_apply_payment(self):
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-security-view")]
        )
        payment = self._create_incoming_payment(20)
        payment.action_post()
        allocation = self.env["pos.customer.debt.allocation"].create(
            {
                "payment_id": payment.id,
                "order_id": orders["debt-security-view"].id,
                "amount": 20,
            }
        )
        viewer = self.env["res.users"].create(
            {
                "name": "Debt Viewer",
                "login": "debt-viewer",
                "group_ids": [
                    Command.set(
                        [
                            self.env.ref(
                                "pos_customer_debt.group_pos_customer_debt_viewer"
                            ).id,
                            self.env.ref("point_of_sale.group_pos_user").id,
                        ]
                    )
                ],
            }
        )

        self.assertTrue(allocation.with_user(viewer).check_access("read") is None)
        self.assertEqual(
            allocation.with_user(viewer).read(
                ["payment_reference", "effective_amount", "state"]
            )[0]["effective_amount"],
            0,
        )
        self.assertEqual(
            orders["debt-security-view"].with_user(viewer).debt_residual_amount,
            100,
        )
        with self.assertRaises(AccessError):
            allocation.with_user(viewer).action_apply()
