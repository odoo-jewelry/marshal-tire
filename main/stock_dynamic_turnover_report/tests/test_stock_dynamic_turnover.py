from datetime import datetime, time, timedelta
from io import BytesIO
import json
from types import SimpleNamespace
from zipfile import ZipFile

from freezegun import freeze_time

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestStockDynamicTurnover(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([
            ("company_id", "=", cls.company.id)], limit=1)
        cls.location_a = cls.warehouse.lot_stock_id
        cls.location_b = cls.env["stock.location"].create({
            "name": "Dynamic turnover B", "usage": "internal",
            "company_id": cls.company.id,
            "location_id": cls.warehouse.view_location_id.id,
        })
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.customer = cls.env.ref("stock.stock_location_customers")
        cls.period_day = fields.Date.today() - timedelta(days=2)
        cls.before_day = cls.period_day - timedelta(days=1)
        cls.category = cls.env["product.category"].create({
            "name": "Dynamic FIFO", "property_cost_method": "fifo",
        })
        with freeze_time(datetime.combine(cls.before_day - timedelta(days=1), time(9))):
            cls.product = cls.env["product.product"].create({
                "name": "=Dynamic stock", "is_storable": True,
                "categ_id": cls.category.id, "standard_price": 100,
            })
        cls.service = cls.env["stock.dynamic.turnover.report"]

    def _move(self, quantity, source, destination, day, value=None, hour=10, purchase_line=None):
        vals = {
            "company_id": self.company.id, "product_id": self.product.id,
            "product_uom": self.product.uom_id.id, "product_uom_qty": quantity,
            "location_id": source.id, "location_dest_id": destination.id,
        }
        if value is not None:
            vals["value_manual"] = value
        if purchase_line:
            vals["purchase_line_id"] = purchase_line.id
        with freeze_time(datetime.combine(day, time(hour))):
            move = self.env["stock.move"].create(vals)
            move._action_confirm(merge=False)
            move.quantity = quantity
            move.picked = True
            move._action_done()
        return move

    def _options(self, mode="stock", **extra):
        return {
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [self.product.id],
            "mode": mode,
            "row_dimensions": ["product"] if mode == "stock" else ["receipt", "product"],
            **extra,
        }

    def _report(self, mode="stock", **extra):
        return self.service.get_report(self._options(mode, **extra))

    def test_stock_boundary_and_internal_transfer(self):
        self._move(10, self.supplier, self.location_a, self.before_day, 1000)
        self._move(3, self.location_a, self.location_b, self.period_day)
        whole = self._report(row_dimensions=["warehouse", "product"])
        self.assertEqual(whole["totals"]["opening_qty"][self.product.uom_id.id], 10)
        self.assertEqual(whole["totals"]["closing_qty"][self.product.uom_id.id], 10)
        self.assertFalse(whole["totals"]["incoming_qty"])
        self.assertFalse(whole["totals"]["outgoing_qty"])
        first = self._report(location_ids=[self.location_a.id], include_children=False)
        second = self._report(location_ids=[self.location_b.id], include_children=False)
        self.assertEqual(first["totals"]["outgoing_qty"][self.product.uom_id.id], 3)
        self.assertEqual(second["totals"]["incoming_qty"][self.product.uom_id.id], 3)
        self.assertEqual(first["totals"]["outgoing_value"], second["totals"]["incoming_value"])

        row = next(item for item in first["rows"] if item["level"] == 1)
        detail = self.service.get_details(first["options"], row["key"], "opening", first["revision"])
        self.assertEqual(sum(event["quantity"] for event in detail["events"]), 10)
        self.assertEqual(sum(event["amount"] for event in detail["events"]), row["measures"]["opening_value"])
        self.assertTrue(all(event["allocation_basis"] == "company_valuation_allocation"
                            for event in detail["events"]))
        self.assertTrue(all(event["document_model"] in ("stock.quant", "stock.move")
                            for event in detail["events"]))

    def test_fifo_receipts_split_recorded_cost(self):
        first = self._move(10, self.supplier, self.location_a, self.before_day, 1000, hour=10)
        second = self._move(5, self.supplier, self.location_a, self.before_day, 600, hour=11)
        self._move(12, self.location_a, self.customer, self.period_day, 1240)
        report = self._report("receipts")
        receipts = {row["path"][0][1]: row for row in report["rows"] if row["level"] == 1}
        self.assertEqual(receipts[first.id]["measures"]["outgoing_qty"][self.product.uom_id.id], 10)
        self.assertEqual(receipts[second.id]["measures"]["outgoing_qty"][self.product.uom_id.id], 2)
        self.assertEqual(receipts[first.id]["measures"]["outgoing_value"], 1000)
        self.assertEqual(receipts[second.id]["measures"]["outgoing_value"], 240)
        self.assertEqual(report["totals"]["closing_qty"][self.product.uom_id.id], 3)
        self.assertEqual(report["totals"]["closing_value"], 360)
        self.assertFalse(report["diagnostics"])
        self.assertIn("No PO", receipts[first.id]["label"])

    def test_fifo_filter_after_full_history(self):
        first = self._move(10, self.supplier, self.location_a, self.before_day, 1000, hour=10)
        second = self._move(5, self.supplier, self.location_a, self.before_day, 600, hour=11)
        self._move(12, self.location_a, self.customer, self.period_day, 1240)
        report = self._report("receipts", receipt_ids=[second.id])
        self.assertEqual(report["totals"]["closing_qty"][self.product.uom_id.id], 3)
        self.assertEqual(report["totals"]["outgoing_qty"][self.product.uom_id.id], 2)
        self.assertFalse(any(row["path"] and row["path"][0][1] == first.id
                             for row in report["rows"]))

    def test_invalid_modes_and_access(self):
        with self.assertRaises(UserError):
            self._report("receipts", location_ids=[self.location_a.id])
        with self.assertRaises(UserError):
            self._report("stock", receipt_ids=[1])
        with self.assertRaises(UserError):
            self._report(row_dimensions=["product", "product"])
        with self.assertRaises(UserError):
            self._report(date_to=(fields.Date.today() + timedelta(days=1)).isoformat())
        with self.assertRaises(AccessError):
            self._report(company_id=999999999)
        ordinary = new_test_user(self.env, login="dynamic-stock-ordinary",
                                 groups="stock.group_stock_user")
        with self.assertRaises(AccessError):
            self.service.with_user(ordinary).get_report(self._options())
        outside = self.env["stock.location"].create({
            "name": "Outside selected warehouse", "usage": "internal",
            "company_id": self.company.id,
        })
        with self.assertRaises(UserError):
            self._report(warehouse_ids=[self.warehouse.id], location_ids=[outside.id])
        manager = new_test_user(self.env, login="dynamic-stock-manager-only",
                                groups="stock.group_stock_manager",
                                company_id=self.company.id)
        self.assertEqual(
            self.service.with_user(manager).get_report(self._options())["mode"], "stock")

    def test_revision_details_and_read_only(self):
        move = self._move(3, self.supplier, self.location_a, self.period_day, 300)
        before = (move.value, move.state, move.quantity)
        report = self._report()
        product_row = next(row for row in report["rows"] if row["level"] == 1)
        detail = self.service.get_details(report["options"], product_row["key"],
                                          "incoming", report["revision"])
        self.assertEqual(sum(event["quantity"] for event in detail["events"]), 3)
        self.assertEqual((move.value, move.state, move.quantity), before)
        repeated = self.service.get_report(report["options"])
        self.assertEqual(repeated["revision"], report["revision"])
        move.value = 330
        with self.assertRaises(UserError):
            self.service.get_details(report["options"], product_row["key"],
                                     "incoming", report["revision"])
        with self.assertRaises(UserError):
            self.service.get_xlsx_report(
                json.dumps({"options": report["options"], "revision": report["revision"]}),
                SimpleNamespace(stream=BytesIO()), "Stock Turnover",
                "stock_dynamic_turnover_report.action_stock_dynamic_turnover")

    def test_xlsx_uses_server_values_and_safe_text(self):
        self._move(3, self.supplier, self.location_a, self.period_day, 300)
        report = self._report()
        response = SimpleNamespace(stream=BytesIO())
        payload = json.dumps({"options": report["options"], "revision": report["revision"],
                              "rows": [{"label": "forged"}]})
        with self.assertRaises(UserError):
            self.service.get_xlsx_report(
                payload, response, "Stock Turnover",
                "stock_dynamic_turnover_report.action_stock_dynamic_turnover")
        self.service.get_xlsx_report(
            json.dumps({"options": report["options"], "revision": report["revision"]}),
            response, "Stock Turnover",
            "stock_dynamic_turnover_report.action_stock_dynamic_turnover")
        with ZipFile(BytesIO(response.stream.getvalue())) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml")
            self.assertNotIn(b"<f>", sheet)
            self.assertIn(b"300", sheet)
            self.assertIn(b"=Dynamic stock", archive.read("xl/sharedStrings.xml"))

    def test_no_tracking_or_foreign_owner(self):
        unstorable = self.env["product.product"].create({"name": "Service", "is_storable": False})
        with self.assertRaises(UserError):
            self._report(product_ids=[unstorable.id])
        foreign = self.env["res.partner"].create({"name": "Foreign owner"})
        with freeze_time(datetime.combine(self.before_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": self.product.id,
                "product_uom": self.product.uom_id.id, "product_uom_qty": 4,
                "location_id": self.supplier.id, "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 4
            move.move_line_ids.owner_id = foreign
            move.picked = True
            move._action_done()
        report = self._report()
        self.assertFalse(report["totals"]["opening_qty"])

    def test_same_timestamp_receipt_and_issue_are_unattributed(self):
        self._move(2, self.supplier, self.location_a, self.before_day, 200)
        self._move(1, self.supplier, self.location_a, self.period_day, 100, hour=10)
        self._move(1, self.location_a, self.customer, self.period_day, 100, hour=10)
        report = self._report("receipts")
        self.assertTrue(any(reason["code"] == "ambiguous_same_time"
                            for reason in report["diagnostics"]))
        self.assertTrue(any(row["path"] and row["path"][0][1] == 0
                            for row in report["rows"]))

    def test_more_than_one_hundred_fifo_receipts(self):
        receipts = [self._move(1, self.supplier, self.location_a, self.before_day,
                               1, hour=10) for _ in range(101)]
        report = self._report("receipts", page_size=200)
        row_ids = {row["path"][0][1] for row in report["rows"] if row["level"] == 1}
        self.assertEqual(row_ids, {move.id for move in receipts})
        self.assertEqual(report["totals"]["closing_qty"][self.product.uom_id.id], 101)
        self.assertEqual(report["totals"]["closing_value"], 101)
        paged = self._report("receipts", page_size=20)
        self.assertEqual(paged["page_count"], 6)
        response = SimpleNamespace(stream=BytesIO())
        self.service.get_xlsx_report(
            json.dumps({"options": paged["options"], "revision": paged["revision"]}),
            response, "Stock Turnover",
            "stock_dynamic_turnover_report.action_stock_dynamic_turnover")
        with ZipFile(BytesIO(response.stream.getvalue())) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml")
            self.assertGreater(sheet.count(b"<row "), 200)

    def test_lot_valuated_fifo_receipt(self):
        product = self.env["product.product"].create({
            "name": "Dynamic valued lot", "is_storable": True,
            "categ_id": self.category.id, "tracking": "lot", "lot_valuated": True,
        })
        lot = self.env["stock.lot"].create({
            "name": "Dynamic lot", "product_id": product.id,
            "company_id": self.company.id,
        })
        with freeze_time(datetime.combine(self.before_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": product.id,
                "product_uom": product.uom_id.id, "product_uom_qty": 2,
                "value_manual": 40, "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 2
            move.move_line_ids.lot_id = lot
            move.picked = True
            move._action_done()
        report = self._report("receipts", product_ids=[product.id])
        receipt = next(row for row in report["rows"] if row["level"] == 1
                       and row["path"][0][1] == move.id)
        self.assertEqual(receipt["measures"]["closing_qty"][product.uom_id.id], 2)
        self.assertEqual(receipt["measures"]["closing_value"], 40)

    def test_purchase_order_filter_and_label(self):
        partner = self.env["res.partner"].create({"name": "Dynamic supplier"})
        order = self.env["purchase.order"].create({"partner_id": partner.id})
        line = self.env["purchase.order.line"].create({
            "order_id": order.id, "name": "Dynamic product",
            "product_id": self.product.id, "product_qty": 2,
            "product_uom_id": self.product.uom_id.id, "price_unit": 100,
            "date_planned": fields.Datetime.now(),
        })
        receipt = self._move(2, self.supplier, self.location_a,
                             self.before_day, 200, purchase_line=line)
        report = self._report("receipts", purchase_order_ids=[order.id])
        row = next(item for item in report["rows"] if item["level"] == 1)
        self.assertIn(order.name, row["label"])
        self.assertEqual(row["path"][0][1], receipt.id)
        self.assertEqual(report["totals"]["closing_qty"][self.product.uom_id.id], 2)
        manager = new_test_user(self.env, login="dynamic-stock-no-purchase",
                                groups="stock.group_stock_manager",
                                company_id=self.company.id)
        limited = self.service.with_user(manager)
        visible = limited.get_report(self._options("receipts"))
        self.assertTrue(any(item["path"] and item["path"][0][1] == receipt.id
                            for item in visible["rows"]))
        suggestions = limited.get_filter_values(self._options("receipts"),
                                                "receipt_ids", order.name[:3])
        if not self.env["purchase.order"].with_user(manager).has_access("read"):
            self.assertFalse(any(order.name in item["name"] for item in suggestions))
            self.assertFalse(any(order.name in item["label"] for item in visible["rows"]))

    def test_archived_product_and_hidden_history(self):
        self._move(2, self.supplier, self.location_a, self.before_day, 200)
        self.product.active = False
        report = self._report()
        self.assertEqual(report["totals"]["opening_qty"][self.product.uom_id.id], 2)
        manager = new_test_user(self.env, login="dynamic-stock-restricted",
                                groups="stock.group_stock_manager",
                                company_id=self.company.id)
        self.env["ir.rule"].create({
            "name": "Dynamic report restricted movement history",
            "model_id": self.env.ref("stock.model_stock_move_line").id,
            "domain_force": "[('id', '=', 0)]",
            "groups": [Command.link(self.env.ref("stock.group_stock_manager").id)],
            "perm_read": True, "perm_write": False,
            "perm_create": False, "perm_unlink": False,
        })
        with self.assertRaises(AccessError):
            self.service.with_user(manager).get_report(self._options())

    def test_operation_priority(self):
        inventory = self.env["stock.location"].create({
            "name": "Dynamic inventory adjustment", "usage": "inventory",
            "company_id": self.company.id,
        })
        picking = SimpleNamespace(
            _fields={"historical_pos_order_id": True},
            historical_pos_order_id=False, pos_order_id=True, pos_session_id=False,
        )
        move = SimpleNamespace(
            picking_id=picking, scrap_id=False,
            sale_line_id=True, purchase_line_id=True,
        )
        line = SimpleNamespace(
            move_id=move, location_id=self.location_a,
            location_dest_id=self.customer,
        )
        scope = {self.location_a.id, self.location_b.id}
        self.assertEqual(self.service._operation(line, scope), "pos_sale")
        picking.historical_pos_order_id = True
        self.assertEqual(self.service._operation(line, scope), "historical_writeoff")
        picking.historical_pos_order_id = False
        move.scrap_id = True
        self.assertEqual(self.service._operation(line, scope), "scrap")
        move.scrap_id = False
        line.location_dest_id = self.location_b
        self.assertEqual(self.service._operation(line, scope), "internal_transfer")
        line.location_id = self.customer
        line.location_dest_id = self.location_a
        self.assertEqual(self.service._operation(line, scope), "customer_return")
        line.location_id = self.location_a
        line.location_dest_id = self.supplier
        self.assertEqual(self.service._operation(line, scope), "supplier_return")
        line.location_id = inventory
        line.location_dest_id = self.location_a
        self.assertEqual(self.service._operation(line, scope), "inventory_gain")
        line.location_id = self.location_a
        line.location_dest_id = inventory
        self.assertEqual(self.service._operation(line, scope), "inventory_loss")
        line.location_dest_id = self.customer
        picking.pos_order_id = False
        self.assertEqual(self.service._operation(line, scope), "sale_delivery")
        move.sale_line_id = False
        self.assertEqual(self.service._operation(line, scope), "other")
        line.location_id = self.supplier
        line.location_dest_id = self.location_a
        self.assertEqual(self.service._operation(line, scope), "supplier_receipt")
        move.purchase_line_id = False
        self.assertEqual(self.service._operation(line, scope), "supplier_receipt")

    def test_split_receipt_pack_and_column_layout(self):
        pack = self.env.ref("uom.product_uom_pack_6")
        with freeze_time(datetime.combine(self.period_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": self.product.id,
                "product_uom": pack.id, "product_uom_qty": 1,
                "value_manual": 600, "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            self.env["stock.move.line"].create([
                {
                    "move_id": move.id, "company_id": self.company.id,
                    "product_id": self.product.id, "product_uom_id": pack.id,
                    "quantity": 0.5, "picked": True,
                    "location_id": self.supplier.id,
                    "location_dest_id": self.location_a.id,
                },
                {
                    "move_id": move.id, "company_id": self.company.id,
                    "product_id": self.product.id, "product_uom_id": pack.id,
                    "quantity": 0.5, "picked": True,
                    "location_id": self.supplier.id,
                    "location_dest_id": self.location_b.id,
                },
            ])
            move._action_done()
            draft = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": self.product.id,
                "product_uom": self.product.uom_id.id, "product_uom_qty": 99,
                "location_id": self.supplier.id, "location_dest_id": self.location_a.id,
            })
            canceled = draft.copy()
            canceled._action_confirm(merge=False)
            canceled._action_cancel()
        first = self._report(location_ids=[self.location_a.id],
                             include_children=False, columns="operations")
        second = self._report(location_ids=[self.location_b.id],
                              include_children=False, columns="operations")
        unit_id = self.product.uom_id.id
        self.assertEqual(first["totals"]["incoming_qty"][unit_id], 3)
        self.assertEqual(second["totals"]["incoming_qty"][unit_id], 3)
        self.assertEqual(first["totals"]["incoming_value"], 300)
        self.assertEqual(second["totals"]["incoming_value"], 300)
        self.assertEqual(first["totals"]["closing_qty"][unit_id], 3)
        self.assertEqual(sum(operation["quantity"].get(unit_id, 0)
                             for operation in first["rows"][0]["operations"].values()), 3)
        reordered = self._report(
            row_dimensions=["category", "warehouse", "product"], columns="operations")
        original = self._report(
            row_dimensions=["warehouse", "category", "product"], columns="operations")
        self.assertEqual(reordered["totals"], original["totals"])
        self.assertNotEqual(reordered["rows"][1]["path"], original["rows"][1]["path"])

    def test_non_fifo_and_unattributed_shortage(self):
        standard_category = self.env["product.category"].create({
            "name": "Dynamic standard", "property_cost_method": "standard",
        })
        standard = self.env["product.product"].create({
            "name": "Dynamic standard product", "is_storable": True,
            "categ_id": standard_category.id, "standard_price": 10,
        })
        with freeze_time(datetime.combine(self.before_day, time(9))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": standard.id,
                "product_uom": standard.uom_id.id, "product_uom_qty": 2,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 2
            move.picked = True
            move._action_done()
        report = self._report("receipts", product_ids=[standard.id])
        self.assertEqual(report["rows"][1]["path"][0][1], -1)
        self.assertIn("not_applicable", report["rows"][1]["diagnostics"])
        self._move(1, self.supplier, self.location_a, self.before_day, 100)
        self._move(3, self.location_a, self.customer, self.period_day, 300)
        shortage = self._report("receipts")
        self.assertTrue(any(reason["code"] in (
            "fifo_stack_quantity_mismatch", "insufficient_fifo_history")
            for reason in shortage["diagnostics"]))
        self.assertTrue(any(row["path"] and row["path"][0][1] == 0
                            for row in shortage["rows"]))

    def test_export_and_details_reject_unprivileged_user(self):
        self._move(2, self.supplier, self.location_a, self.period_day, 200)
        report = self._report()
        row = next(item for item in report["rows"] if item["level"] == 1)
        ordinary = new_test_user(self.env, login="dynamic-stock-export-ordinary",
                                 groups="stock.group_stock_user")
        limited = self.service.with_user(ordinary)
        with self.assertRaises(AccessError):
            limited.get_details(report["options"], row["key"], "incoming", report["revision"])
        with self.assertRaises(AccessError):
            limited.get_xlsx_report(
                json.dumps({"options": report["options"], "revision": report["revision"]}),
                SimpleNamespace(stream=BytesIO()), "Stock Turnover",
                "stock_dynamic_turnover_report.action_stock_dynamic_turnover")

    def test_customer_return_is_a_new_receipt(self):
        first = self._move(2, self.supplier, self.location_a, self.before_day, 200)
        self._move(1, self.location_a, self.customer, self.before_day, 100, hour=11)
        returned = self._move(1, self.customer, self.location_a, self.period_day, 100)
        report = self._report("receipts")
        ids = {row["path"][0][1] for row in report["rows"] if row["level"] == 1}
        self.assertIn(first.id, ids)
        self.assertIn(returned.id, ids)
        returned_row = next(row for row in report["rows"] if row["level"] == 1
                            and row["path"][0][1] == returned.id)
        self.assertEqual(returned_row["measures"]["incoming_qty"][self.product.uom_id.id], 1)
        self.assertEqual(returned_row["operations"]["customer_return"]["quantity"][self.product.uom_id.id], 1)
        self.assertIn("No PO", returned_row["label"])

    def test_local_day_boundary_and_mixed_units(self):
        previous_timezone = self.env.user.tz
        self.env.user.tz = "Asia/Tokyo"
        try:
            self._move(1, self.supplier, self.location_a, self.before_day, 100, hour=14)
            self._move(1, self.supplier, self.location_a, self.before_day, 100, hour=15)
            first = self._report()
            unit_id = self.product.uom_id.id
            self.assertEqual(first["totals"]["opening_qty"][unit_id], 1)
            self.assertEqual(first["totals"]["incoming_qty"][unit_id], 1)
            self.assertEqual(first["totals"]["closing_qty"][unit_id], 2)
        finally:
            self.env.user.tz = previous_timezone
        kilogram = self.env.ref("uom.product_uom_kgm")
        other = self.env["product.product"].create({
            "name": "Dynamic kilograms", "is_storable": True,
            "categ_id": self.category.id, "uom_id": kilogram.id,
            "standard_price": 10,
        })
        with freeze_time(datetime.combine(self.period_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": other.id,
                "product_uom": kilogram.id, "product_uom_qty": 2,
                "value_manual": 20, "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 2
            move.picked = True
            move._action_done()
        mixed = self._report(
            product_ids=[self.product.id, other.id],
            row_dimensions=["category"])
        self.assertEqual(mixed["totals"]["closing_qty"][unit_id], 2)
        self.assertEqual(mixed["totals"]["closing_qty"][kilogram.id], 2)
        self.assertEqual(len(mixed["totals"]["closing_qty"]), 2)

    def test_fractional_cost_allocation_and_average_value(self):
        with freeze_time(datetime.combine(self.period_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": self.product.id,
                "product_uom": self.product.uom_id.id, "product_uom_qty": 3,
                "value_manual": 10, "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            self.env["stock.move.line"].create([
                {
                    "move_id": move.id, "company_id": self.company.id,
                    "product_id": self.product.id,
                    "product_uom_id": self.product.uom_id.id,
                    "quantity": quantity, "picked": True,
                    "location_id": self.supplier.id,
                    "location_dest_id": location.id,
                }
                for quantity, location in ((1, self.location_a), (2, self.location_b))
            ])
            move._action_done()
        first = self._report(location_ids=[self.location_a.id], include_children=False)
        second = self._report(location_ids=[self.location_b.id], include_children=False)
        self.assertEqual(first["totals"]["incoming_value"], 3.33)
        self.assertEqual(second["totals"]["incoming_value"], 6.67)
        self.assertEqual(first["totals"]["incoming_value"] + second["totals"]["incoming_value"], move.value)
        average_category = self.env["product.category"].create({
            "name": "Dynamic average", "property_cost_method": "average",
        })
        average = self.env["product.product"].create({
            "name": "Dynamic average product", "is_storable": True,
            "categ_id": average_category.id, "standard_price": 5,
        })
        with freeze_time(datetime.combine(self.period_day, time(11))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id, "product_id": average.id,
                "product_uom": average.uom_id.id, "product_uom_qty": 3,
                "value_manual": 30, "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 3
            move.picked = True
            move._action_done()
        report = self._report(product_ids=[average.id])
        self.assertEqual(report["totals"]["incoming_value"], 30)
        self.assertEqual(report["totals"]["closing_value"], 30)
