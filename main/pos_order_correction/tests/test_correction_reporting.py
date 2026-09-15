from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionReporting(PosOrderCorrectionCommon):
    def test_sales_and_accounting_keep_original_period_and_post_only_difference(self):
        order = self._create_paid_order("correction-report-periods")
        original_date = fields.Datetime.now() - timedelta(days=35)
        order.date_order = original_date
        self._close_session(self.session)
        original_session = self.session
        original_move = original_session.move_id
        original_lines = original_move.line_ids.read([
            "account_id", "debit", "credit", "date", "balance",
        ])
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        correction = self._prepare(order)
        correction.line_ids.write({"product_id": self.product80.id, "price_unit": 120})
        correction.payment_ids.amount = 120
        correction.reason = "Correct an earlier period sale"
        correction.action_apply()
        self._close_session(self.session)
        difference = correction.applied_order_id
        self.env.flush_all()

        report = self.env["report.pos.order"]
        historical = report.search([("order_id", "=", order.id)])
        current = report.search([("order_id", "=", difference.id)])
        self.assertEqual(historical.product_id, self.product100)
        self.assertEqual(historical.date, original_date)
        self.assertEqual(sum(historical.mapped("price_total")), 100)
        self.assertEqual(sum(current.mapped("price_total")), 20)
        self.assertEqual(sum(current.filtered(
            lambda line: line.product_id == self.product100
        ).mapped("price_total")), -100)
        self.assertEqual(sum(current.filtered(
            lambda line: line.product_id == self.product80
        ).mapped("price_total")), 120)
        self.assertGreater(difference.date_order, original_date)
        self.assertEqual(original_session.state, "closed")
        self.assertEqual(original_move.line_ids.read([
            "account_id", "debit", "credit", "date", "balance",
        ]), original_lines)
        revenue = self.session.move_id.line_ids.filtered(
            lambda line: line.account_id.account_type == "income"
        )
        self.assertEqual(-sum(revenue.mapped("balance")), 20)
