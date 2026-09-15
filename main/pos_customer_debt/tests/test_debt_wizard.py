from odoo.tests import tagged

from .common import PosCustomerDebtCommon


@tagged("post_install", "-at_install")
class TestPosCustomerDebtPaymentRegister(PosCustomerDebtCommon):
    def test_register_payment_uses_explicit_distribution(self):
        _session, orders = self._close_orders(
            [
                self._pay_later_order_values("debt-wizard-1"),
                self._pay_later_order_values("debt-wizard-2"),
            ]
        )
        order1 = orders["debt-wizard-1"]
        order2 = orders["debt-wizard-2"]
        action = (order1 | order2).action_register_debt_payment()
        wizard = self.env["account.payment.register"].with_context(
            **action["context"]
        ).create({})
        wizard.amount = 70
        wizard.pos_debt_allocation_line_ids.filtered(
            lambda line: line.order_id == order1
        ).amount = 20
        wizard.pos_debt_allocation_line_ids.filtered(
            lambda line: line.order_id == order2
        ).amount = 50

        payments = wizard._create_payments()
        repeated_payments = wizard._create_payments()

        self.assertEqual(len(payments), 1)
        self.assertEqual(repeated_payments, payments)
        self.assertEqual(payments.amount, 70)
        self.assertEqual(order1.debt_residual_amount, 80)
        self.assertEqual(order2.debt_residual_amount, 50)
        self.assertEqual(len(payments.pos_debt_allocation_ids), 2)

    def test_regular_payment_posting_is_unchanged(self):
        payment = self._create_incoming_payment(25)

        payment.action_post()

        self.assertIn(payment.state, ("in_process", "paid"))
        self.assertFalse(payment.pos_debt_allocation_ids)
        self.assertEqual(payment.pos_debt_available_amount, 25)
