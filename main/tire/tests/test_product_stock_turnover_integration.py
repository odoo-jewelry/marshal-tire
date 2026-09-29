from datetime import datetime
from io import BytesIO
from zipfile import ZipFile

from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged

from odoo.addons.pos_order_correction.tests.common import PosOrderCorrectionCommon
from odoo.addons.purchase_cost_recompute.tests.common import PurchaseCostRecomputeCommon


@tagged("post_install", "-at_install")
class TestTurnoverAppliedPurchaseCorrection(PurchaseCostRecomputeCommon):
    def test_applied_purchase_cost_and_report_reads_only(self):
        order = self._purchase(date="2026-01-01 10:00:00")
        receipt = order.order_line.move_ids
        original_value = receipt.value
        order._apply_purchase_cost_recompute()
        self.assertNotEqual(receipt.value, original_value)
        service = self.env["stock.product.turnover.report"]
        options = {
            "company_id": self.company.id,
            "date_from": "2026-01-01",
            "date_to": "2026-01-01",
            "product_ids": [self.product.id],
            "show_fifo_receipts": True,
        }
        sources_before = {
            "move": receipt.read(["value", "quantity", "date", "state"]),
            "line": receipt.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "purchase": order.read(["amount_total", "state"]),
            "product_values": self.env["product.value"].search_count([]),
            "pos_orders": self.env["pos.order"].search_count([]),
            "account_moves": self.env["account.move"].search_count([]),
        }
        report = service.get_report(options)
        row = next(item for item in report["rows"] if item["product_id"] == self.product.id)
        self.assertEqual(row["incoming_qty"], receipt.quantity)
        self.assertEqual(row["incoming_value"], receipt.value)
        self.assertEqual(row["fifo_receipts"]["closing"]["receipts"][0]["unit_cost"],
                         receipt.value / receipt.quantity)
        self.assertEqual(service.get_report(report["options"])["fingerprint"], report["fingerprint"])
        detail = service.get_details(
            report["options"], self.product.id, "incoming", report["fingerprint"],
        )
        self.assertEqual(sum(line["amount"] for line in detail["lines"]), row["incoming_value"])
        with ZipFile(BytesIO(service.get_xlsx(report["options"], report["fingerprint"]))) as archive:
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
        sources_after = {
            "move": receipt.read(["value", "quantity", "date", "state"]),
            "line": receipt.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "purchase": order.read(["amount_total", "state"]),
            "product_values": self.env["product.value"].search_count([]),
            "pos_orders": self.env["pos.order"].search_count([]),
            "account_moves": self.env["account.move"].search_count([]),
        }
        self.assertEqual(sources_before, sources_after)


@tagged("post_install", "-at_install")
class TestTurnoverAppliedHistoricalWriteoff(PosOrderCorrectionCommon):
    def test_applied_historical_writeoff_and_report_reads_only(self):
        self.env.user.group_ids = [
            Command.link(self.env.ref("pos_historical_stock_writeoff.group_historical_stock").id),
            Command.link(self.env.ref("stock.group_stock_manager").id),
        ]
        category = self.categ_basic.copy({
            "name": "Turnover historical integration",
            "property_cost_method": "fifo",
        })
        product = self.create_product("Turnover historical product", category, 100, 100)
        location = self.config.picking_type_id.default_location_src_id
        with freeze_time("2026-01-01 10:00:00"):
            receipt = self.env["stock.move"].create({
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 5,
                "value_manual": 500,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": location.id,
                "company_id": self.company.id,
            })
            receipt._action_confirm(merge=False)
            receipt.quantity = 5
            receipt.picked = True
            receipt._action_done()
        with freeze_time("2026-01-02 10:00:00"):
            session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
        with freeze_time("2026-01-02 11:00:00"):
            self._close_session(session)
        if not self.config.current_session_id:
            self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
        source = self.env["pos.order"].create({
            "session_id": self.config.current_session_id.id,
            "state": "cancel",
            "amount_total": 0, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({
                "product_id": product.id, "qty": 1,
                "price_unit": 0, "price_subtotal": 0, "price_subtotal_incl": 0,
            })],
        })
        action = source.action_prepare_historical_stock()
        picking = self.env["stock.picking"].browse(action["res_id"])
        picking.write({
            "historical_session_id": session.id,
            "historical_reason": "Integration report verification",
        })
        picking.action_apply_historical_stock()
        historical_move = picking.move_ids
        self.assertEqual(historical_move.date, datetime(2026, 1, 2, 11))
        service = self.env["stock.product.turnover.report"]
        options = {
            "company_id": self.company.id,
            "date_from": "2026-01-02",
            "date_to": "2026-01-02",
            "product_ids": [product.id],
            "show_fifo_receipts": True,
        }
        before = {
            "moves": (receipt | historical_move).read(["value", "quantity", "date", "state"]),
            "lines": historical_move.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "pos": source.read(["state", "amount_total", "lines"]),
            "account_moves": self.env["account.move"].search_count([]),
        }
        report = service.get_report(options)
        row = next(item for item in report["rows"] if item["product_id"] == product.id)
        self.assertEqual((row["opening_qty"], row["outgoing_qty"], row["closing_qty"]), (5, 1, 4))
        self.assertEqual(row["outgoing_value"], historical_move.value)
        self.assertEqual(row["fifo_receipts"]["opening"]["receipts"][0]["quantity"], 5)
        self.assertEqual(row["fifo_receipts"]["closing"]["receipts"][0]["quantity"], 4)
        self.assertEqual(service.get_report(report["options"])["fingerprint"], report["fingerprint"])
        service.get_details(report["options"], product.id, "outgoing", report["fingerprint"])
        service.get_xlsx(report["options"], report["fingerprint"])
        after = {
            "moves": (receipt | historical_move).read(["value", "quantity", "date", "state"]),
            "lines": historical_move.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "pos": source.read(["state", "amount_total", "lines"]),
            "account_moves": self.env["account.move"].search_count([]),
        }
        self.assertEqual(before, after)
