from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionPosSync(PosOrderCorrectionCommon):
    def _ownership_echo(self):
        return {
            "correction_root_id": False,
            "correction_id": False,
            "is_correction_order": False,
            "correction_return_root_id": False,
            "correction_ids": [],
            "correction_order_ids": [],
            "correction_has_external_settlement": False,
        }

    def _sync_order(self, values):
        self.env["pos.order"].with_context(generate_pdf=False).sync_from_ui([values])
        return self.env["pos.order"].search([("uuid", "=", values["uuid"])])

    def test_draft_payment_accepts_empty_correction_metadata(self):
        self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        uuid = "correction-sync-ordinary"
        draft_values = self.create_ui_order_data(
            [(self.product100, 1)], customer=self.customer, payments=[], uuid=uuid,
            pos_order_ui_args={"state": "draft", **self._ownership_echo()},
        )
        order = self._sync_order(draft_values)
        self.assertEqual(order.state, "draft")

        paid_values = self.create_ui_order_data(
            [(self.product100, 1)], customer=self.customer,
            payments=[(self.cash_pm1, 100)], uuid=uuid,
            pos_order_ui_args={"state": "paid", **self._ownership_echo()},
        )
        paid_values["lines"] = []
        self.assertEqual(self._sync_order(paid_values), order)
        self.assertEqual(order.state, "paid")
        self.assertEqual(len(order.lines), 1)
        self.assertEqual(order.amount_paid, 100)
        self.assertFalse(order.is_correction_order)
        self.assertFalse(order.correction_root_id)

    def test_return_payment_preserves_server_assigned_root(self):
        sale = self._create_paid_order("correction-sync-return-source")
        correction = self._prepare(sale)
        correction.line_ids.price_unit = 120
        correction.payment_ids.amount = 120
        correction.reason = "Wrong price"
        correction.action_apply()
        self._close_session(self.session)
        self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        source = sale._get_effective_correction_lines()
        line_values = [{
            "product": source.product_id,
            "quantity": -1,
            "price_unit": 120,
            "price_subtotal": -120,
            "price_subtotal_incl": -120,
            "refunded_orderline_id": source.id,
        }]
        uuid = "correction-sync-return"
        draft_values = self.create_ui_order_data(
            line_values, customer=self.customer, payments=[], uuid=uuid,
            pos_order_ui_args={"state": "draft", **self._ownership_echo()},
        )
        refund = self._sync_order(draft_values)
        self.assertEqual(refund.state, "draft")
        self.assertEqual(refund.correction_return_root_id, sale)

        paid_values = self.create_ui_order_data(
            line_values, customer=self.customer, payments=[(self.cash_pm1, -120)], uuid=uuid,
            pos_order_ui_args={
                "state": "paid", **self._ownership_echo(),
                "correction_return_root_id": sale.id,
            },
        )
        paid_values["lines"] = []
        self.assertEqual(self._sync_order(paid_values), refund)
        self.assertEqual(refund.state, "paid")
        self.assertEqual(refund.correction_return_root_id, sale)
        self.assertEqual(refund.lines.refunded_orderline_id, source)
        self.assertEqual(refund.amount_paid, -120)

    def test_client_cannot_assign_correction_ownership(self):
        sale = self._create_paid_order("correction-sync-forged-source")
        correction = self._prepare(sale)
        forged_values = {
            "correction_root_id": sale.id,
            "correction_id": correction.id,
            "is_correction_order": True,
            "correction_return_root_id": sale.id,
            "correction_ids": [Command.link(correction.id)],
            "correction_order_ids": [Command.link(sale.id)],
            "correction_has_external_settlement": True,
        }
        uuid = "correction-sync-forged"
        for state, payments in (("draft", []), ("paid", [(self.cash_pm1, 100)])):
            values = self.create_ui_order_data(
                [(self.product100, 1)], customer=self.customer, payments=payments, uuid=uuid,
                pos_order_ui_args={"state": state, **forged_values},
            )
            if state == "paid":
                values["lines"] = []
            order = self._sync_order(values)
            self.assertEqual(order.state, state)
            for field_name in forged_values:
                self.assertFalse(order[field_name], field_name)
            self.assertEqual(correction.root_order_id, sale)
            self.assertFalse(sale.correction_root_id)

        with self.assertRaises(UserError):
            order.write({"is_correction_order": True})
        with self.assertRaises(UserError):
            self.env["pos.order"].create({"is_correction_order": True})
