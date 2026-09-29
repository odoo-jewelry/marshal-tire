from datetime import datetime, time, timedelta
from io import BytesIO
from zipfile import ZipFile

from freezegun import freeze_time
from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestProductStockTurnover(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([
            ("company_id", "=", cls.company.id),
        ], limit=1)
        cls.location_a = cls.warehouse.lot_stock_id
        cls.location_b = cls.env["stock.location"].create({
            "name": "Turnover B",
            "usage": "internal",
            "company_id": cls.company.id,
            "location_id": cls.warehouse.view_location_id.id,
        })
        cls.supplier = cls.env.ref("stock.stock_location_suppliers")
        cls.customer = cls.env.ref("stock.stock_location_customers")
        cls.period_day = fields.Date.today() - timedelta(days=2)
        cls.before_day = cls.period_day - timedelta(days=1)
        cls.category = cls.env["product.category"].create({
            "name": "Turnover standard",
            "property_cost_method": "standard",
        })
        with freeze_time(datetime.combine(cls.before_day - timedelta(days=1), time(10))):
            cls.product = cls.env["product.product"].create({
                "name": "Turnover checked product",
                "is_storable": True,
                "categ_id": cls.category.id,
                "standard_price": 100,
            })
        cls.report_model = cls.env["stock.product.turnover.report"]

    def _move(self, quantity, source, destination, day, value=None):
        values = {
            "company_id": self.company.id,
            "product_id": self.product.id,
            "product_uom": self.product.uom_id.id,
            "product_uom_qty": quantity,
            "location_id": source.id,
            "location_dest_id": destination.id,
        }
        if value is not None:
            values["value_manual"] = value
        with freeze_time(datetime.combine(day, time(10))):
            move = self.env["stock.move"].create(values)
            move._action_confirm(merge=False)
            move.quantity = quantity
            move.picked = True
            move._action_done()
        return move

    def _options(self, **extra):
        return {
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [self.product.id],
            **extra,
        }

    def _row(self, **extra):
        report = self.report_model.get_report(self._options(**extra))
        return report, next(row for row in report["rows"] if row["product_id"] == self.product.id)

    def test_completed_quantity_and_standard_value(self):
        self._move(10, self.supplier, self.location_a, self.before_day, value=1000)
        self._move(2, self.location_a, self.customer, self.period_day)
        report, row = self._row()
        self.assertEqual(
            (row["opening_qty"], row["incoming_qty"], row["outgoing_qty"], row["closing_qty"]),
            (10, 0, 2, 8),
        )
        self.assertEqual(row["opening_value"], 1000)
        self.assertEqual(row["closing_value"], 800)
        self.assertEqual(row["outgoing_value"], 200)
        self.assertEqual(row["valuation_difference"], 0)
        self.assertFalse(row["diagnostics"])
        repeated = self.report_model.get_report(report["options"])
        self.assertEqual(report["fingerprint"], repeated["fingerprint"])

    def test_internal_transfer_uses_one_cost_and_whole_scope_has_no_turnover(self):
        self._move(10, self.supplier, self.location_a, self.before_day, value=1000)
        self._move(3, self.location_a, self.location_b, self.period_day)
        _whole, warehouse_row = self._row(warehouse_id=self.warehouse.id)
        _a, source_row = self._row(location_id=self.location_a.id, include_children=False)
        _b, destination_row = self._row(location_id=self.location_b.id, include_children=False)
        self.assertEqual((warehouse_row["incoming_qty"], warehouse_row["outgoing_qty"]), (0, 0))
        self.assertEqual((source_row["outgoing_qty"], destination_row["incoming_qty"]), (3, 3))
        self.assertEqual((source_row["outgoing_value"], destination_row["incoming_value"]), (300, 300))

    def test_invalid_filters_and_direct_access(self):
        with self.assertRaises(UserError):
            self.report_model.get_report(self._options(date_to=(fields.Date.today() + timedelta(days=1)).isoformat()))
        with self.assertRaises(UserError):
            self.report_model.get_report(self._options(date_from=(self.period_day + timedelta(days=1)).isoformat()))
        ordinary = new_test_user(self.env, login="turnover-ordinary", groups="stock.group_stock_user")
        with self.assertRaises(AccessError):
            self.report_model.with_user(ordinary).get_report(self._options())
        with self.assertRaises(AccessError):
            self.report_model.with_user(ordinary).get_xlsx(self._options(), "0" * 64)
        with self.assertRaises(AccessError):
            self.report_model.with_user(ordinary).get_details(
                self._options(), self.product.id, "opening", "0" * 64,
            )

    def test_stale_detail_and_export(self):
        move = self._move(10, self.supplier, self.location_a, self.before_day, value=1000)
        report, row = self._row()
        detail = self.report_model.get_details(
            report["options"], self.product.id, "opening", report["fingerprint"],
        )
        self.assertEqual(detail["explanation"]["quantity"], row["opening_qty"])
        move.value = 1100
        with self.assertRaises(UserError):
            self.report_model.get_details(
                report["options"], self.product.id, "opening", report["fingerprint"],
            )
        with self.assertRaises(UserError):
            self.report_model.get_xlsx(report["options"], report["fingerprint"])

    def test_export_is_numeric_and_has_no_formula_cells(self):
        self.product.name = "=Turnover formula"
        self._move(10, self.supplier, self.location_a, self.before_day, value=1000)
        report, _row = self._row()
        content = self.report_model.get_xlsx(report["options"], report["fingerprint"])
        with ZipFile(BytesIO(content)) as archive:
            sheet = archive.read("xl/worksheets/sheet1.xml")
            self.assertNotIn(b"<f>", sheet)
            root = etree.fromstring(sheet)
            cells = root.xpath(
                ".//s:c[@r='E14']", namespaces={"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"},
            )
            self.assertEqual(cells[0].findtext("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v"), "10")
            self.assertNotEqual(cells[0].get("t"), "s")
            self.assertIn(b"=Turnover formula", archive.read("xl/sharedStrings.xml"))

    def test_foreign_owner_and_archived_variant(self):
        foreign = self.env["res.partner"].create({"name": "Other stock owner"})
        with freeze_time(datetime.combine(self.before_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 4,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 4
            move.move_line_ids.owner_id = foreign
            move.picked = True
            move._action_done()
        excluded = self.report_model.get_report(self._options())
        self.assertFalse(any(row["product_id"] == self.product.id for row in excluded["rows"]))
        self._move(2, self.supplier, self.location_a, self.before_day, value=200)
        self.product.active = False
        _report, row = self._row()
        self.assertEqual(row["opening_qty"], 2)

    def test_hidden_movement_history_is_rejected_before_value(self):
        from odoo import Command

        self._move(2, self.supplier, self.location_a, self.before_day, value=200)
        manager = new_test_user(
            self.env, login="turnover-restricted", groups="stock.group_stock_manager",
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        allowed = self.report_model.with_user(manager)
        self.assertEqual(next(row for row in allowed.get_report(self._options())["rows"]
                              if row["product_id"] == self.product.id)["opening_qty"], 2)
        self.env["ir.rule"].create({
            "name": "Turnover restricted movement history",
            "model_id": self.env.ref("stock.model_stock_move_line").id,
            "domain_force": "[('id', '=', 0)]",
            "groups": [Command.link(self.env.ref("stock.group_stock_manager").id)],
            "perm_read": True,
            "perm_write": False,
            "perm_create": False,
            "perm_unlink": False,
        })
        with self.assertRaises(AccessError):
            allowed.get_report(self._options())

    def test_shared_variant_remains_company_isolated(self):
        from odoo import Command

        self.product.company_id = False
        self._move(10, self.supplier, self.location_a, self.before_day, value=1000)
        other = self.env["res.company"].create({"name": "Turnover second company"})
        other_warehouse = self.env["stock.warehouse"].search([("company_id", "=", other.id)], limit=1)
        other_location = other_warehouse.lot_stock_id
        with freeze_time(datetime.combine(self.before_day - timedelta(days=1), time(11))):
            self.product.with_company(other).standard_price = 1000
        with freeze_time(datetime.combine(self.before_day, time(11))):
            move = self.env["stock.move"].with_company(other).create({
                "company_id": other.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 5,
                "value_manual": 5000,
                "location_id": self.supplier.id,
                "location_dest_id": other_location.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 5
            move.picked = True
            move._action_done()
        manager = new_test_user(
            self.env, login="turnover-multicompany", groups="stock.group_stock_manager",
            company_id=self.company.id,
            company_ids=[Command.set((self.company | other).ids)],
        )
        multi = self.report_model.with_user(manager).with_context(
            allowed_company_ids=[self.company.id, other.id],
        )
        first = multi.get_report(self._options())
        second = multi.get_report(self._options(company_id=other.id))
        first_row = next(row for row in first["rows"] if row["product_id"] == self.product.id)
        second_row = next(row for row in second["rows"] if row["product_id"] == self.product.id)
        self.assertEqual((first_row["opening_qty"], second_row["opening_qty"]), (10, 5))
        self.assertEqual((first_row["opening_value"], second_row["opening_value"]), (1000, 5000))

    def test_local_calendar_boundary(self):
        from odoo import Command

        manager = new_test_user(
            self.env, login="turnover-tz", groups="stock.group_stock_manager",
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
            tz="Europe/Kyiv",
        )
        with freeze_time(datetime.combine(self.period_day, time(21, 30))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 1,
                "value_manual": 100,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 1
            move.picked = True
            move._action_done()
        local_day = self.period_day + timedelta(days=1)
        report = self.report_model.with_user(manager).get_report({
            "company_id": self.company.id,
            "date_from": local_day.isoformat(),
            "date_to": local_day.isoformat(),
            "product_ids": [self.product.id],
        })
        row = next(row for row in report["rows"] if row["product_id"] == self.product.id)
        self.assertEqual((row["opening_qty"], row["incoming_qty"], row["closing_qty"]), (0, 1, 1))

    def test_average_and_fifo_match_standard_past_endpoint(self):
        for method in ("average", "fifo"):
            category = self.env["product.category"].create({
                "name": "Turnover " + method,
                "property_cost_method": method,
            })
            product = self.env["product.product"].create({
                "name": "Turnover " + method,
                "is_storable": True,
                "categ_id": category.id,
            })
            for day, quantity, unit_price in (
                (self.before_day, 10, 100),
                (self.period_day, 10, 200),
            ):
                with freeze_time(datetime.combine(day, time(10))):
                    move = self.env["stock.move"].create({
                        "company_id": self.company.id,
                        "product_id": product.id,
                        "product_uom": product.uom_id.id,
                        "product_uom_qty": quantity,
                        "value_manual": quantity * unit_price,
                        "location_id": self.supplier.id,
                        "location_dest_id": self.location_a.id,
                    })
                    move._action_confirm(merge=False)
                    move.quantity = quantity
                    move.picked = True
                    move._action_done()
            report = self.report_model.get_report({
                "company_id": self.company.id,
                "date_from": self.period_day.isoformat(),
                "date_to": self.period_day.isoformat(),
                "product_ids": [product.id],
            })
            row = next(item for item in report["rows"] if item["product_id"] == product.id)
            with self.subTest(method=method):
                self.assertEqual((row["opening_qty"], row["incoming_qty"], row["closing_qty"]), (10, 10, 20))
                self.assertEqual((row["opening_value"], row["incoming_value"], row["closing_value"]), (1000, 2000, 3000))
                self.assertEqual(row["valuation_difference"], 0)
                end = datetime.combine(self.period_day + timedelta(days=1), time.min) - timedelta(microseconds=1)
                standard_value = product.with_company(self.company)._with_valuation_context().with_context(
                    to_date=end, allowed_company_ids=self.company.ids,
                ).total_value
                self.assertEqual(row["closing_value"], standard_value)

    def test_lot_values_are_allocated_within_each_lot(self):
        category = self.env["product.category"].create({
            "name": "Turnover lot AVCO",
            "property_cost_method": "average",
        })
        product = self.env["product.product"].create({
            "name": "Turnover valued lots",
            "is_storable": True,
            "categ_id": category.id,
            "tracking": "lot",
            "lot_valuated": True,
        })
        lot_1, lot_2 = self.env["stock.lot"].create([
            {"name": "Turnover lot 1", "product_id": product.id, "company_id": self.company.id},
            {"name": "Turnover lot 2", "product_id": product.id, "company_id": self.company.id},
        ])
        def move(quantity, source, destination, day, lot, value=None):
            with freeze_time(datetime.combine(day, time(10))):
                values = {
                    "company_id": self.company.id,
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": quantity,
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                }
                if value is not None:
                    values["value_manual"] = value
                operation = self.env["stock.move"].create(values)
                operation._action_confirm(merge=False)
                operation.quantity = quantity
                operation.move_line_ids.lot_id = lot
                operation.picked = True
                operation._action_done()
        move(10, self.supplier, self.location_a, self.before_day, lot_1, 1000)
        move(10, self.supplier, self.location_a, self.before_day, lot_2, 2000)
        move(5, self.location_a, self.location_b, self.period_day, lot_1)
        report = self.report_model.get_report({
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [product.id],
            "location_id": self.location_a.id,
            "include_children": False,
        })
        row = next(item for item in report["rows"] if item["product_id"] == product.id)
        self.assertEqual((row["opening_qty"], row["outgoing_qty"], row["closing_qty"]), (20, 5, 15))
        self.assertEqual((row["opening_value"], row["outgoing_value"], row["closing_value"]), (3000, 500, 2500))

    def test_product_category_and_warehouse_filters_intersect(self):
        self._move(3, self.supplier, self.location_a, self.before_day, value=300)
        other_category = self.env["product.category"].create({"name": "Other turnover category"})
        other_product = self.env["product.product"].create({
            "name": "Other turnover product",
            "is_storable": True,
            "categ_id": other_category.id,
        })
        report = self.report_model.get_report(self._options(
            product_ids=[self.product.id, other_product.id],
            category_ids=[self.category.id],
            warehouse_id=self.warehouse.id,
        ))
        self.assertEqual([row["product_id"] for row in report["rows"]], [self.product.id])
        outside = self.env["stock.location"].create({
            "name": "Outside turnover warehouse",
            "usage": "internal",
            "company_id": self.company.id,
        })
        with self.assertRaises(UserError):
            self.report_model.get_report(self._options(
                warehouse_id=self.warehouse.id,
                location_id=outside.id,
            ))

    def test_zero_closing_row_and_current_history_diagnostic(self):
        self._move(5, self.supplier, self.location_a, self.before_day, value=500)
        self._move(5, self.location_a, self.customer, self.period_day)
        _report, row = self._row()
        self.assertEqual((row["opening_qty"], row["closing_qty"]), (5, 0))
        quant = self.env["stock.quant"].search([
            ("product_id", "=", self.product.id),
            ("location_id", "=", self.location_a.id),
            ("owner_id", "=", False),
        ], limit=1)
        quant.quantity = 1
        _changed, row = self._row()
        self.assertTrue(any(item["code"] == "unexplained_current_quantity" for item in row["diagnostics"]))

    def test_planned_cancelled_and_package_quantity(self):
        pack = self.env.ref("uom.product_uom_pack_6")
        with freeze_time(datetime.combine(self.period_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": pack.id,
                "product_uom_qty": 2,
                "value_manual": 1200,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 2
            move.picked = True
            move._action_done()
            planned = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 100,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            cancelled = planned.copy()
            cancelled._action_confirm(merge=False)
            cancelled._action_cancel()
        _report, row = self._row()
        self.assertEqual((row["incoming_qty"], row["closing_qty"]), (12, 12))
        self.assertEqual(row["incoming_value"], 1200)

    def test_split_receipt_uses_actual_locations_and_proportional_value(self):
        with freeze_time(datetime.combine(self.period_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 5,
                "value_manual": 500,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            self.env["stock.move.line"].create([
                {
                    "move_id": move.id,
                    "company_id": self.company.id,
                    "product_id": self.product.id,
                    "product_uom_id": self.product.uom_id.id,
                    "quantity": 2,
                    "picked": True,
                    "location_id": self.supplier.id,
                    "location_dest_id": self.location_a.id,
                },
                {
                    "move_id": move.id,
                    "company_id": self.company.id,
                    "product_id": self.product.id,
                    "product_uom_id": self.product.uom_id.id,
                    "quantity": 3,
                    "picked": True,
                    "location_id": self.supplier.id,
                    "location_dest_id": self.location_b.id,
                },
            ])
            move._action_done()
        _report, row = self._row(location_id=self.location_a.id, include_children=False)
        self.assertEqual((row["incoming_qty"], row["incoming_value"]), (2, 200))

    def test_returns_inventory_and_scrap_follow_location_direction(self):
        inventory = self.env["stock.location"].create({
            "name": "Turnover inventory adjustment",
            "usage": "inventory",
            "company_id": self.company.id,
        })
        scrap = self.env["stock.location"].create({
            "name": "Turnover scrap",
            "usage": "inventory",
            "company_id": self.company.id,
        })
        self._move(2, self.customer, self.location_a, self.period_day, value=200)
        self._move(1, inventory, self.location_a, self.period_day, value=100)
        self._move(1, self.location_a, self.supplier, self.period_day)
        self._move(1, self.location_a, scrap, self.period_day)
        _report, row = self._row()
        self.assertEqual((row["incoming_qty"], row["outgoing_qty"], row["closing_qty"]), (3, 2, 1))

    def test_zero_company_quantity_reports_unavailable_location_value(self):
        self._move(5, self.location_a, self.location_b, self.period_day)
        _report, source = self._row(location_id=self.location_a.id, include_children=False)
        self.assertEqual(source["closing_qty"], -5)
        self.assertIsNone(source["closing_value"])
        self.assertIsNone(source["outgoing_value"])
        self.assertTrue(any(item["code"] == "zero_valuation_denominator" for item in source["diagnostics"]))

    def test_negative_company_quantity_and_outside_warehouse_location(self):
        self._move(2, self.location_a, self.customer, self.period_day)
        _negative_report, negative = self._row()
        self.assertEqual(negative["closing_qty"], -2)
        outside = self.env["stock.location"].create({
            "name": "Turnover valued outside warehouse",
            "usage": "internal",
            "company_id": self.company.id,
        })
        self._move(4, self.supplier, outside, self.period_day, value=400)
        _company_report, company_row = self._row()
        _warehouse_report, warehouse_row = self._row(warehouse_id=self.warehouse.id)
        self.assertEqual(company_row["closing_qty"], 2)
        self.assertEqual(warehouse_row["closing_qty"], -2)

    def test_exact_local_midnight_is_in_following_day(self):
        with freeze_time(datetime.combine(self.period_day, time.min)):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 1,
                "value_manual": 100,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 1
            move.picked = True
            move._action_done()
        previous = (self.period_day - timedelta(days=1)).isoformat()
        report_before = self.report_model.get_report(self._options(date_from=previous, date_to=previous))
        report_after = self.report_model.get_report(self._options())
        self.assertFalse(any(row["product_id"] == self.product.id for row in report_before["rows"]))
        row = next(row for row in report_after["rows"] if row["product_id"] == self.product.id)
        self.assertEqual((row["opening_qty"], row["incoming_qty"]), (0, 1))

    def test_standard_lot_past_value_is_marked_unavailable(self):
        product = self.env["product.product"].create({
            "name": "Turnover standard lot",
            "is_storable": True,
            "categ_id": self.category.id,
            "tracking": "lot",
            "lot_valuated": True,
        })
        lot = self.env["stock.lot"].create({
            "name": "Turnover standard lot number",
            "product_id": product.id,
            "company_id": self.company.id,
        })
        with freeze_time(datetime.combine(self.before_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 1,
                "value_manual": 100,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 1
            move.move_line_ids.lot_id = lot
            move.picked = True
            move._action_done()
        report = self.report_model.get_report({
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [product.id],
        })
        row = next(item for item in report["rows"] if item["product_id"] == product.id)
        self.assertIsNone(row["opening_value"])
        self.assertTrue(any(item["code"] == "missing_historical_lot_basis" for item in row["diagnostics"]))

    def test_external_valuation_context_does_not_change_report(self):
        self._move(3, self.supplier, self.location_a, self.before_day, value=300)
        normal, row = self._row()
        hostile = self.report_model.with_context(
            warehouse_id=999999,
            location=[999999],
            owners=[999999],
            fifo_qty_already_processed={self.product: 999999},
            pos_historical_fifo_date=datetime.combine(self.period_day, time.min),
            allowed_company_ids=self.company.ids,
        ).get_report(normal["options"])
        other = next(item for item in hostile["rows"] if item["product_id"] == self.product.id)
        self.assertEqual(row["opening_value"], other["opening_value"])
        self.assertEqual(normal["fingerprint"], hostile["fingerprint"])

    def test_other_location_receipt_creates_explained_difference(self):
        category = self.env["product.category"].create({
            "name": "Turnover allocation average",
            "property_cost_method": "average",
        })
        product = self.env["product.product"].create({
            "name": "Turnover allocation",
            "is_storable": True,
            "categ_id": category.id,
        })
        def receipt(destination, day, value):
            with freeze_time(datetime.combine(day, time(10))):
                move = self.env["stock.move"].create({
                    "company_id": self.company.id,
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": 10,
                    "value_manual": value,
                    "location_id": self.supplier.id,
                    "location_dest_id": destination.id,
                })
                move._action_confirm(merge=False)
                move.quantity = 10
                move.picked = True
                move._action_done()
        receipt(self.location_a, self.before_day, 1000)
        receipt(self.location_b, self.period_day, 2000)
        report = self.report_model.get_report({
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [product.id],
            "location_id": self.location_a.id,
            "include_children": False,
        })
        row = next(item for item in report["rows"] if item["product_id"] == product.id)
        self.assertEqual(
            (row["opening_qty"], row["incoming_qty"], row["outgoing_qty"], row["closing_qty"]),
            (10, 0, 0, 10),
        )
        self.assertEqual(
            (row["opening_value"], row["incoming_value"], row["outgoing_value"],
             row["closing_value"], row["valuation_difference"]),
            (1000, 0, 0, 1500, 500),
        )
        detail = self.report_model.get_details(
            report["options"], product.id, "difference", report["fingerprint"],
        )
        self.assertEqual(detail["explanation"]["difference"], 500)

    def test_same_timestamp_internal_moves_share_pre_timestamp_cost(self):
        category = self.env["product.category"].create({
            "name": "Turnover same timestamp average",
            "property_cost_method": "average",
        })
        product = self.env["product.product"].create({
            "name": "Turnover timestamp",
            "is_storable": True,
            "categ_id": category.id,
        })
        def perform(quantity, source, destination, day, value=None):
            with freeze_time(datetime.combine(day, time(10))):
                values = {
                    "company_id": self.company.id,
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": quantity,
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                }
                if value is not None:
                    values["value_manual"] = value
                move = self.env["stock.move"].create(values)
                move._action_confirm(merge=False)
                move.quantity = quantity
                move.picked = True
                move._action_done()
        perform(10, self.supplier, self.location_a, self.before_day, 1000)
        perform(10, self.supplier, self.location_b, self.period_day, 2000)
        perform(3, self.location_a, self.location_b, self.period_day)
        perform(2, self.location_a, self.location_b, self.period_day)
        report = self.report_model.get_report({
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [product.id],
            "location_id": self.location_a.id,
            "include_children": False,
        })
        row = next(item for item in report["rows"] if item["product_id"] == product.id)
        self.assertEqual((row["outgoing_qty"], row["outgoing_value"]), (5, 500))
        details = self.report_model.get_details(
            report["options"], product.id, "outgoing", report["fingerprint"],
        )
        self.assertEqual(sorted(line["amount"] for line in details["lines"]), [200, 300])

    def test_internal_cost_cache_refreshes_after_company_receipt(self):
        category = self.env["product.category"].create({
            "name": "Turnover cost epoch average",
            "property_cost_method": "average",
        })
        product = self.env["product.product"].create({
            "name": "Turnover cost epoch product",
            "is_storable": True,
            "categ_id": category.id,
        })

        def perform(hour, source, destination, value=None):
            values = {
                "company_id": self.company.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 1 if value is None else 10,
                "location_id": source.id,
                "location_dest_id": destination.id,
            }
            if value is not None:
                values["value_manual"] = value
            with freeze_time(datetime.combine(self.period_day, time(hour))):
                move = self.env["stock.move"].create(values)
                move._action_confirm(merge=False)
                move.quantity = values["product_uom_qty"]
                move.picked = True
                move._action_done()
            return move

        perform(9, self.supplier, self.location_a, 1000)
        perform(10, self.location_a, self.location_b)
        perform(11, self.supplier, self.location_a, 3000)
        perform(12, self.location_a, self.location_b)
        report = self.report_model.get_report({
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [product.id],
            "location_id": self.location_a.id,
            "include_children": False,
        })
        detail = self.report_model.get_details(
            report["options"], product.id, "outgoing", report["fingerprint"],
        )
        self.assertEqual(sorted(line["amount"] for line in detail["lines"]), [100, 200])

    def test_fractional_external_allocation_and_recorded_zero(self):
        with freeze_time(datetime.combine(self.period_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 3,
                "value_manual": 100,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            self.env["stock.move.line"].create([
                {
                    "move_id": move.id, "company_id": self.company.id,
                    "product_id": self.product.id, "product_uom_id": self.product.uom_id.id,
                    "quantity": 1, "picked": True,
                    "location_id": self.supplier.id, "location_dest_id": self.location_a.id,
                },
                {
                    "move_id": move.id, "company_id": self.company.id,
                    "product_id": self.product.id, "product_uom_id": self.product.uom_id.id,
                    "quantity": 2, "picked": True,
                    "location_id": self.supplier.id, "location_dest_id": self.location_b.id,
                },
            ])
            move._action_done()
        _a, row_a = self._row(location_id=self.location_a.id, include_children=False)
        _b, row_b = self._row(location_id=self.location_b.id, include_children=False)
        self.assertEqual((row_a["incoming_value"], row_b["incoming_value"]), (33.33, 66.67))
        self.assertEqual(row_a["incoming_value"] + row_b["incoming_value"], 100)
        zero = self._move(1, self.supplier, self.location_a, self.period_day)
        zero.value = 0
        self.assertEqual(zero.value, 0)
        _report, row = self._row()
        self.assertEqual(row["incoming_value"], 100)
        self.assertFalse(any(item["code"] == "missing_movement_denominator" for item in row["diagnostics"]))

    def test_different_lots_in_one_internal_move_keep_distinct_costs(self):
        category = self.env["product.category"].create({
            "name": "Turnover mixed lot average",
            "property_cost_method": "average",
        })
        product = self.env["product.product"].create({
            "name": "Turnover mixed lots",
            "is_storable": True,
            "tracking": "lot",
            "lot_valuated": True,
            "categ_id": category.id,
        })
        lot_1, lot_2 = self.env["stock.lot"].create([
            {"name": "Turnover mixed lot 1", "product_id": product.id, "company_id": self.company.id},
            {"name": "Turnover mixed lot 2", "product_id": product.id, "company_id": self.company.id},
        ])
        for lot, value in ((lot_1, 100), (lot_2, 200)):
            with freeze_time(datetime.combine(self.before_day, time(10))):
                move = self.env["stock.move"].create({
                    "company_id": self.company.id,
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": 1,
                    "value_manual": value,
                    "location_id": self.supplier.id,
                    "location_dest_id": self.location_a.id,
                })
                move._action_confirm(merge=False)
                move.quantity = 1
                move.move_line_ids.lot_id = lot
                move.picked = True
                move._action_done()
        with freeze_time(datetime.combine(self.period_day, time(10))):
            transfer = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 2,
                "location_id": self.location_a.id,
                "location_dest_id": self.location_b.id,
            })
            transfer._action_confirm(merge=False)
            self.env["stock.move.line"].create([
                {
                    "move_id": transfer.id, "company_id": self.company.id,
                    "product_id": product.id, "product_uom_id": product.uom_id.id,
                    "quantity": 1, "picked": True, "lot_id": lot.id,
                    "location_id": self.location_a.id, "location_dest_id": self.location_b.id,
                }
                for lot in (lot_1, lot_2)
            ])
            transfer._action_done()
        report = self.report_model.get_report({
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": [product.id],
            "location_id": self.location_a.id,
            "include_children": False,
        })
        row = next(item for item in report["rows"] if item["product_id"] == product.id)
        detail = self.report_model.get_details(
            report["options"], product.id, "outgoing", report["fingerprint"],
        )
        self.assertEqual(row["outgoing_value"], 300)
        self.assertEqual(sorted(line["amount"] for line in detail["lines"]), [100, 200])

    def test_mixed_owners_share_only_owned_valued_denominator(self):
        foreign = self.env["res.partner"].create({"name": "Turnover foreign owner"})
        with freeze_time(datetime.combine(self.period_day, time(10))):
            move = self.env["stock.move"].create({
                "company_id": self.company.id,
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 5,
                "value_manual": 200,
                "location_id": self.supplier.id,
                "location_dest_id": self.location_a.id,
            })
            move._action_confirm(merge=False)
            self.env["stock.move.line"].create([
                {
                    "move_id": move.id, "company_id": self.company.id,
                    "product_id": self.product.id, "product_uom_id": self.product.uom_id.id,
                    "quantity": 2, "picked": True,
                    "location_id": self.supplier.id, "location_dest_id": self.location_a.id,
                },
                {
                    "move_id": move.id, "company_id": self.company.id,
                    "product_id": self.product.id, "product_uom_id": self.product.uom_id.id,
                    "quantity": 3, "picked": True, "owner_id": foreign.id,
                    "location_id": self.supplier.id, "location_dest_id": self.location_b.id,
                },
            ])
            move._action_done()
        _report, row = self._row()
        self.assertEqual((row["incoming_qty"], row["incoming_value"]), (2, 200))

    def test_full_result_totals_and_xlsx_exceed_display_page(self):
        with freeze_time(datetime.combine(self.period_day, time(10))):
            products = self.env["product.product"].create([
                {
                    "name": "Turnover page %02d" % number,
                    "is_storable": True,
                    "categ_id": self.category.id,
                }
                for number in range(51)
            ])
            moves = self.env["stock.move"].create([
                {
                    "company_id": self.company.id,
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": 1,
                    "value_manual": 1,
                    "location_id": self.supplier.id,
                    "location_dest_id": self.location_a.id,
                }
                for product in products
            ])
            moves._action_confirm(merge=False)
            moves.quantity = 1
            moves.picked = True
            moves._action_done()
        report = self.report_model.get_report({
            "company_id": self.company.id,
            "date_from": self.period_day.isoformat(),
            "date_to": self.period_day.isoformat(),
            "product_ids": products.ids,
        })
        self.assertEqual(len(report["rows"]), 51)
        self.assertEqual(report["totals"]["incoming_value"], 51)
        self.assertEqual(report["unit_totals"][0]["incoming_qty"], 51)
        payload = self.report_model.get_xlsx(report["options"], report["fingerprint"])
        with ZipFile(BytesIO(payload)) as archive:
            strings = archive.read("xl/sharedStrings.xml")
            self.assertIn(b"Turnover page 00", strings)
            self.assertIn(b"Turnover page 50", strings)

    def test_detail_amounts_match_summary_and_document_links(self):
        self._move(10, self.supplier, self.location_a, self.before_day, value=1000)
        self._move(2, self.location_a, self.customer, self.period_day)
        report, row = self._row()
        opening = self.report_model.get_details(
            report["options"], self.product.id, "opening", report["fingerprint"],
        )
        outgoing = self.report_model.get_details(
            report["options"], self.product.id, "outgoing", report["fingerprint"],
        )
        self.assertEqual(sum(line["quantity"] for line in opening["lines"]), row["opening_qty"])
        self.assertEqual(sum(line["quantity"] for line in outgoing["lines"]), row["outgoing_qty"])
        self.assertEqual(sum(line["amount"] for line in outgoing["lines"]), row["outgoing_value"])
        self.assertTrue(all(line["document_model"] and line["document_id"] for line in outgoing["lines"]))
        self.assertEqual(opening["explanation"]["company_quantity"], 10)
        self.assertEqual(opening["explanation"]["standard_value"], 1000)

    def test_stale_quantity_and_source_visibility(self):
        from odoo import Command

        self._move(3, self.supplier, self.location_a, self.before_day, value=300)
        manager = new_test_user(
            self.env, login="turnover-stale", groups="stock.group_stock_manager",
            company_id=self.company.id, company_ids=[Command.set(self.company.ids)],
        )
        service = self.report_model.with_user(manager)
        report = service.get_report(self._options())
        quant = self.env["stock.quant"].search([
            ("product_id", "=", self.product.id),
            ("location_id", "=", self.location_a.id),
            ("owner_id", "=", False),
        ], limit=1)
        quant.quantity = 4
        with self.assertRaises(UserError):
            service.get_xlsx(report["options"], report["fingerprint"])
        refreshed = service.get_report(report["options"])
        self.env["ir.rule"].create({
            "name": "Turnover stale source restriction",
            "model_id": self.env.ref("stock.model_stock_quant").id,
            "domain_force": "[('id', '=', 0)]",
            "groups": [Command.link(self.env.ref("stock.group_stock_manager").id)],
            "perm_read": True, "perm_write": False, "perm_create": False, "perm_unlink": False,
        })
        with self.assertRaises(AccessError):
            service.get_details(
                refreshed["options"], self.product.id, "opening", refreshed["fingerprint"],
            )

    def test_export_ignores_forged_totals_and_marks_incomplete(self):
        self._move(5, self.location_a, self.location_b, self.period_day)
        report, row = self._row(location_id=self.location_a.id, include_children=False)
        self.assertIsNone(row["closing_value"])
        forged = dict(report["options"], totals={"closing_value": 999999}, move_id=999999)
        content = self.report_model.get_xlsx(forged, report["fingerprint"])
        with ZipFile(BytesIO(content)) as archive:
            strings = archive.read("xl/sharedStrings.xml")
            sheet = archive.read("xl/worksheets/sheet1.xml")
            self.assertIn(b"Monetary totals are incomplete.", strings)
            self.assertNotIn(b"999999", sheet)

    def _lot_move(self, product, lot, quantity, source, destination, day, value=None):
        with freeze_time(datetime.combine(day, time(10))):
            values = {
                "company_id": self.company.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": quantity,
                "location_id": source.id,
                "location_dest_id": destination.id,
            }
            if value is not None:
                values["value_manual"] = value
            move = self.env["stock.move"].create(values)
            move._action_confirm(merge=False)
            move.quantity = quantity
            move.move_line_ids.lot_id = lot
            move.picked = True
            move._action_done()
        return move

    def _fifo_product(self, *, tracking="none", lot_valuated=False):
        category = self.env["product.category"].create({
            "name": "Turnover FIFO receipts", "property_cost_method": "fifo",
        })
        self.product = self.env["product.product"].create({
            "name": "FIFO receipt product", "is_storable": True,
            "tracking": tracking, "lot_valuated": lot_valuated,
            "categ_id": category.id,
        })
        return self.product

    def test_fifo_receipts_without_tracking_and_partial_consumption(self):
        self._fifo_product()
        first = self._move(10, self.supplier, self.location_a, self.before_day, value=100)
        second = self._move(5, self.supplier, self.location_a, self.before_day, value=100)
        self._move(12, self.location_a, self.customer, self.period_day)
        plain, plain_row = self._row()
        report, row = self._row(show_fifo_receipts=True)
        self.assertNotIn("fifo_receipts", plain_row)
        self.assertEqual(plain["totals"], report["totals"])
        opening = row["fifo_receipts"]["opening"]
        closing = row["fifo_receipts"]["closing"]
        self.assertTrue(opening["applicable"])
        self.assertEqual([(item["move_id"], item["quantity"], item["unit_cost"])
                          for item in opening["receipts"]],
                         [(first.id, 10, 10), (second.id, 5, 20)])
        self.assertEqual([(item["move_id"], item["quantity"], item["value"])
                          for item in closing["receipts"]], [(second.id, 3, 60)])
        self.assertEqual(closing["unattributed_quantity"], 0)
        self.assertEqual(closing["unattributed_value"], 0)
        self.assertTrue(all(item["lot_id"] is False for item in closing["receipts"]))
        document = self.report_model.get_fifo_receipt_document(
            report["options"], self.product.id, "closing", second.id, 0, report["fingerprint"],
        )
        self.assertEqual(document["document_id"], second.id)
        with self.assertRaises(AccessError):
            self.report_model.get_fifo_receipt_document(
                report["options"], self.product.id, "closing", first.id, 0, report["fingerprint"],
            )
        with ZipFile(BytesIO(self.report_model.get_xlsx(report["options"], report["fingerprint"]))) as archive:
            sheet = etree.fromstring(archive.read("xl/worksheets/sheet2.xml"))
            ns = {"s": sheet.nsmap[None]}
            self.assertFalse(sheet.xpath("//s:f", namespaces=ns))
            self.assertTrue(sheet.xpath("//s:c[@r='H4'][s:v='3']", namespaces=ns))

    def test_fifo_partly_consumed_oldest_receipt(self):
        self._fifo_product()
        first = self._move(10, self.supplier, self.location_a, self.before_day, value=100)
        second = self._move(5, self.supplier, self.location_a, self.before_day, value=100)
        self._move(2, self.location_a, self.customer, self.period_day)
        _report, row = self._row(show_fifo_receipts=True)
        closing = row["fifo_receipts"]["closing"]
        self.assertEqual([(item["move_id"], item["quantity"], item["value"])
                          for item in closing["receipts"]],
                         [(first.id, 8, 80), (second.id, 5, 100)])
        self.assertFalse(closing["diagnostics"])

    def test_fifo_receipts_are_company_basis_for_location_filter(self):
        self._fifo_product()
        first = self._move(4, self.supplier, self.location_a, self.before_day, value=40)
        second = self._move(6, self.supplier, self.location_b, self.before_day, value=120)
        report, row = self._row(show_fifo_receipts=True, location_id=self.location_a.id,
                                include_children=False)
        self.assertEqual(row["closing_qty"], 4)
        basis = row["fifo_receipts"]["closing"]
        self.assertEqual(basis["scope"], "company")
        self.assertTrue(basis["location_selected"])
        self.assertEqual({item["move_id"] for item in basis["receipts"]}, {first.id, second.id})
        self.assertEqual(basis["company_quantity"], 10)
        self.assertEqual(report["options"]["location_id"], self.location_a.id)

    def test_fifo_receipts_revalidate_source_and_access(self):
        self._fifo_product()
        receipt = self._move(2, self.supplier, self.location_a, self.before_day, value=20)
        report, _row = self._row(show_fifo_receipts=True)
        ordinary = new_test_user(self.env, login="turnover-fifo-ordinary", groups="stock.group_stock_user")
        with self.assertRaises(AccessError):
            self.report_model.with_user(ordinary).get_fifo_receipt_document(
                report["options"], self.product.id, "closing", receipt.id, 0,
                report["fingerprint"],
            )
        receipt.value = 30
        with self.assertRaises(UserError):
            self.report_model.get_fifo_receipt_document(
                report["options"], self.product.id, "closing", receipt.id, 0,
                report["fingerprint"],
            )
        refreshed, row = self._row(show_fifo_receipts=True)
        self.assertEqual(row["fifo_receipts"]["closing"]["receipts"][0]["unit_cost"], 15)
        self.assertNotEqual(report["fingerprint"], refreshed["fingerprint"])

    def test_fifo_option_non_fifo_and_lot_valuated(self):
        self._move(1, self.supplier, self.location_a, self.before_day, value=100)
        _report, row = self._row(show_fifo_receipts=True)
        self.assertFalse(row["fifo_receipts"]["closing"]["applicable"])
        with self.assertRaises(UserError):
            self._row(show_lots=True)
        with self.assertRaises(UserError):
            self._row(show_fifo_receipts="yes")
        product = self._fifo_product(tracking="lot", lot_valuated=True)
        lot = self.env["stock.lot"].create({
            "name": "FIFO valuation lot", "product_id": product.id, "company_id": self.company.id,
        })
        receipt = self._lot_move(product, lot, 2, self.supplier, self.location_a,
                                 self.before_day, value=40)
        _report, row = self._row(show_fifo_receipts=True)
        self.assertEqual([(item["move_id"], item["lot_id"], item["quantity"])
                          for item in row["fifo_receipts"]["closing"]["receipts"]],
                         [(receipt.id, lot.id, 2)])

    def test_fifo_zero_and_negative_stock_are_explicit(self):
        self._fifo_product()
        self._move(2, self.supplier, self.location_a, self.before_day, value=20)
        self._move(2, self.location_a, self.customer, self.period_day)
        _report, row = self._row(show_fifo_receipts=True)
        basis = row["fifo_receipts"]["closing"]
        self.assertFalse(basis["receipts"])
        self.assertEqual(basis["unattributed_quantity"], 0)
        self._move(3, self.location_a, self.customer, self.period_day)
        _report, row = self._row(show_fifo_receipts=True)
        basis = row["fifo_receipts"]["closing"]
        self.assertEqual(basis["company_quantity"], -3)
        self.assertFalse(basis["receipts"])
        self.assertEqual(basis["unattributed_quantity"], -3)
        self.assertTrue(basis["diagnostics"])

    def test_fifo_receipts_exceed_initial_standard_stack_batch(self):
        self._fifo_product()
        receipts = [self._move(1, self.supplier, self.location_a, self.before_day,
                               value=1) for _index in range(101)]
        _report, row = self._row(show_fifo_receipts=True)
        closing = row["fifo_receipts"]["closing"]
        self.assertEqual([item["move_id"] for item in closing["receipts"]],
                         [move.id for move in receipts])
        self.assertEqual(sum(item["quantity"] for item in closing["receipts"]), 101)
        self.assertEqual(sum(item["value"] for item in closing["receipts"]), 101)
