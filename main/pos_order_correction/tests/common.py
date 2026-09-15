from odoo import Command
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


class PosOrderCorrectionCommon(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [
            Command.link(cls.env.ref("pos_order_correction.group_pos_order_correction").id)
        ]
        cls.config = cls.basic_config
        cls.product100 = cls.create_product(
            "Correction Product 100", cls.categ_basic, 100, 50
        )
        cls.product80 = cls.create_product(
            "Correction Product 80", cls.categ_basic, 80, 40
        )
        cls.adjust_inventory((cls.product100, cls.product80), (20, 20))

    def _create_paid_order(self, uuid, payment_method=None):
        payment_method = payment_method or self.cash_pm1
        if not self.config.current_session_id:
            self.session = self._start_pos_session(
                self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
            )
        else:
            self.session = self.config.current_session_id
        return self._create_orders(
            [
                {
                    "pos_order_lines_ui_args": [(self.product100, 1)],
                    "payments": [(payment_method, 100)],
                    "customer": self.customer,
                    "is_invoiced": False,
                    "uuid": uuid,
                }
            ]
        )[uuid]

    def _prepare(self, order):
        action = order.action_prepare_correction()
        return self.env["pos.order.correction"].browse(action["res_id"])

    def _close_session(self, session):
        cash_method = session.payment_method_ids.filtered("is_cash_count")[:1]
        cash_total = sum(
            session.order_ids.payment_ids.filtered(
                lambda payment: payment.payment_method_id == cash_method
            ).mapped("amount")
        )
        if cash_method:
            session.post_closing_cash_details(cash_total)
        session.close_session_from_ui()
