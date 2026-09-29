from datetime import datetime
from io import BytesIO
import json
from types import SimpleNamespace
from zipfile import ZipFile

from freezegun import freeze_time

from odoo import Command
from odoo.tests import tagged

from odoo.addons.pos_order_correction.tests.common import PosOrderCorrectionCommon
from odoo.addons.purchase_cost_recompute.tests.common import PurchaseCostRecomputeCommon


ACTION = "stock_dynamic_turnover_report.action_stock_dynamic_turnover"


@tagged("post_install", "-at_install")
class TestDynamicTurnoverPurchaseCorrection(PurchaseCostRecomputeCommon):
    def test_applied_purchase_cost_and_read_only_report(self):
        order = self._purchase(date="2026-01-01 10:00:00")
        receipt = order.order_line.move_ids
        original_value = receipt.value
        order._apply_purchase_cost_recompute()
        self.assertNotEqual(receipt.value, original_value)
        service = self.env["stock.dynamic.turnover.report"]
        options = {
            "company_id": self.company.id, "date_from": "2026-01-01",
            "date_to": "2026-01-01", "product_ids": [self.product.id],
            "mode": "receipts", "row_dimensions": ["receipt", "product"],
        }
        before = {
            "move": receipt.read(["value", "quantity", "date", "state"]),
            "line": receipt.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "purchase": order.read(["amount_total", "state"]),
            "product_values": self.env["product.value"].search_count([]),
            "account_moves": self.env["account.move"].search_count([]),
        }
        financial_before = self.env["account.trial.balance"].view_report()
        report = service.get_report(options)
        self.assertEqual(financial_before, self.env["account.trial.balance"].view_report())
        row = next(item for item in report["rows"] if item["level"] == 1
                   and item["path"][0][1] == receipt.id)
        self.assertEqual(row["measures"]["incoming_qty"][self.product.uom_id.id], receipt.quantity)
        self.assertEqual(row["measures"]["incoming_value"], receipt.value)
        self.assertEqual(service.get_report(report["options"])["revision"], report["revision"])
        detail = service.get_details(report["options"], row["key"], "incoming", report["revision"])
        self.assertEqual(sum(item["amount"] for item in detail["events"]), receipt.value)
        response = SimpleNamespace(stream=BytesIO())
        service.get_xlsx_report(
            json.dumps({"options": report["options"], "revision": report["revision"]}),
            response, "Stock Turnover", ACTION)
        with ZipFile(BytesIO(response.stream.getvalue())) as archive:
            self.assertIn("xl/worksheets/sheet1.xml", archive.namelist())
        after = {
            "move": receipt.read(["value", "quantity", "date", "state"]),
            "line": receipt.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "purchase": order.read(["amount_total", "state"]),
            "product_values": self.env["product.value"].search_count([]),
            "account_moves": self.env["account.move"].search_count([]),
        }
        self.assertEqual(before, after)


@tagged("post_install", "-at_install")
class TestDynamicTurnoverHistoricalWriteoff(PosOrderCorrectionCommon):
    def test_historical_writeoff_is_not_pos_sale(self):
        self.env.user.group_ids = [
            Command.link(self.env.ref("pos_historical_stock_writeoff.group_historical_stock").id),
            Command.link(self.env.ref("stock.group_stock_manager").id),
        ]
        category = self.categ_basic.copy({
            "name": "Dynamic historical integration", "property_cost_method": "fifo",
        })
        product = self.create_product("Dynamic historical product", category, 100, 100)
        location = self.config.picking_type_id.default_location_src_id
        with freeze_time("2026-01-01 10:00:00"):
            receipt = self.env["stock.move"].create({
                "product_id": product.id, "product_uom": product.uom_id.id,
                "product_uom_qty": 5, "value_manual": 500,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": location.id, "company_id": self.company.id,
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
            "state": "cancel", "amount_total": 0, "amount_tax": 0,
            "amount_paid": 0, "amount_return": 0,
            "lines": [Command.create({
                "product_id": product.id, "qty": 1, "price_unit": 0,
                "price_subtotal": 0, "price_subtotal_incl": 0,
            })],
        })
        action = source.action_prepare_historical_stock()
        picking = self.env["stock.picking"].browse(action["res_id"])
        picking.write({
            "historical_session_id": session.id,
            "historical_reason": "Dynamic report verification",
        })
        picking.action_apply_historical_stock()
        historical_move = picking.move_ids
        self.assertEqual(historical_move.date, datetime(2026, 1, 2, 11))
        service = self.env["stock.dynamic.turnover.report"]
        options = {
            "company_id": self.company.id, "date_from": "2026-01-02",
            "date_to": "2026-01-02", "product_ids": [product.id],
            "mode": "stock", "row_dimensions": ["product"], "columns": "operations",
        }
        before = {
            "moves": (receipt | historical_move).read(["value", "quantity", "date", "state"]),
            "lines": historical_move.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "pos": source.read(["state", "amount_total", "lines"]),
        }
        report = service.get_report(options)
        row = next(item for item in report["rows"] if item["level"] == 1)
        self.assertEqual(row["measures"]["outgoing_qty"][product.uom_id.id], 1)
        self.assertEqual(row["operations"]["historical_writeoff"]["quantity"][product.uom_id.id], -1)
        self.assertFalse(row["operations"].get("pos_sale"))
        service.get_details(report["options"], row["key"], "historical_writeoff", report["revision"])
        after = {
            "moves": (receipt | historical_move).read(["value", "quantity", "date", "state"]),
            "lines": historical_move.move_line_ids.read(["quantity_product_uom", "date", "state"]),
            "pos": source.read(["state", "amount_total", "lines"]),
        }
        self.assertEqual(before, after)

    def test_paid_pos_sale_receipt_cell_details(self):
        from datetime import timedelta, time
        from odoo import fields

        day = fields.Date.today() - timedelta(days=1)
        category = self.categ_basic.copy({
            "name": "Dynamic POS FIFO detail", "property_cost_method": "fifo",
        })
        product = self.create_product("Dynamic POS FIFO product", category, 100, 50)
        with freeze_time(datetime.combine(day - timedelta(days=1), time(10))):
            self.adjust_inventory(product, (4,))
        original_product = self.product100
        try:
            self.product100 = product
            with freeze_time(datetime.combine(day, time(11))):
                order = self._create_paid_order("dynamic-pos-receipt-cell")
        finally:
            self.product100 = original_product
        self.assertTrue(order.picking_ids.filtered(lambda picking: picking.state == "done"))
        service = self.env["stock.dynamic.turnover.report"]
        options = {
            "company_id": self.company.id,
            "date_from": day.isoformat(), "date_to": day.isoformat(),
            "product_ids": [product.id], "mode": "receipts",
            "row_dimensions": ["receipt", "product"], "columns": "operations",
        }
        report = service.get_report(options)
        row = next(item for item in report["rows"] if item["level"] == 1
                   and item["operations"].get("pos_sale"))
        pos_cell = row["operations"]["pos_sale"]
        self.assertEqual(pos_cell["quantity"][product.uom_id.id], -1)
        details = service.get_details(
            report["options"], row["key"], "pos_sale", report["revision"])
        self.assertTrue(details["events"])
        self.assertTrue(all(event["operation"] == "pos_sale" for event in details["events"]))
        self.assertEqual(sum(event["quantity"] for event in details["events"]),
                         pos_cell["quantity"][product.uom_id.id])
        self.assertEqual(sum(event["amount"] for event in details["events"]),
                         pos_cell["value"])
