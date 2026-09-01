import base64
import importlib.util
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestPurchaseOrderLineImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.vendor = cls.env["res.partner"].create({
            "name": "Import Test Vendor",
            "supplier_rank": 1,
        })
        cls.uom = cls.env.ref("uom.product_uom_unit")
        cls.product_a = cls.env["product.product"].create({
            "name": "Import Existing A",
            "default_code": "IMP-A",
            "purchase_ok": True,
            "company_id": cls.company.id,
        })
        cls.product_b = cls.env["product.product"].create({
            "name": "Import Existing B",
            "default_code": "IMP-B",
            "barcode": "9900000000012",
            "purchase_ok": True,
            "company_id": cls.company.id,
        })
        cls.import_user = new_test_user(
            cls.env,
            login="purchase_import_manager",
            groups="purchase.group_purchase_manager,product.group_product_manager",
            company_id=cls.company.id,
            company_ids=[Command.set([cls.company.id])],
        )

    def _new_order(self, **values):
        return self.env["purchase.order"].create({
            "partner_id": self.vendor.id,
            "company_id": self.company.id,
            **values,
        })

    def _new_wizard(
        self,
        order,
        csv_content,
        *,
        header_row=1,
        data_row=2,
        unmatched_policy="reject",
        creation_mode="standalone",
        user=None,
        **values,
    ):
        user = user or self.import_user
        return self.env["purchase.order.line.import.wizard"].with_user(user).create({
            "order_id": order.id,
            "file_data": base64.b64encode(csv_content.encode()),
            "file_name": "purchase.csv",
            "header_row": header_row,
            "data_row": data_row,
            "unmatched_policy": unmatched_policy,
            "creation_mode": creation_mode,
            **values,
        })

    def _map(self, wizard, targets):
        wizard.action_parse()
        for mapping in wizard.mapping_ids:
            if mapping.source_column in targets:
                target = targets[mapping.source_column]
                if isinstance(target, tuple):
                    mapping.write({"target": target[0], "attribute_id": target[1].id})
                else:
                    mapping.target = target
        return wizard

    def test_empty_draft_opens_import_action(self):
        order = self._new_order()

        action = order.with_user(self.import_user).action_open_line_import()

        self.assertEqual(
            action["res_model"], "purchase.order.line.import.wizard"
        )
        self.assertEqual(action["context"]["default_order_id"], order.id)

    def test_csv_intro_rows_preview_is_read_only_and_apply_populates_empty_order(self):
        order = self._new_order(origin="HEADER-MUST-STAY")
        unrelated_tier = self.env["product.supplierinfo"].create({
            "partner_id": self.vendor.commercial_partner_id.id,
            "product_id": self.product_a.id,
            "product_tmpl_id": self.product_a.product_tmpl_id.id,
            "company_id": self.company.id,
            "currency_id": order.currency_id.id,
            "product_uom_id": self.uom.id,
            "min_qty": 10,
            "price": 77,
        })
        csv_content = (
            "Purchase export\n"
            "Code,Qty,Price,Description,Min Qty\n"
            "IMP-A,2,12.50,First imported line,0\n"
            "IMP-B,3,8.25,Second imported line,0\n"
        )
        wizard = self._new_wizard(order, csv_content, header_row=2, data_row=3)
        self._map(wizard, {
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
            "Description": "description",
            "Min Qty": "min_qty",
        })
        before = {
            "products": self.env["product.product"].search_count([]),
            "supplierinfos": self.env["product.supplierinfo"].search_count([]),
            "lines": order.order_line.ids,
        }

        wizard.action_preview()

        self.assertTrue(wizard.preview_valid)
        self.assertEqual(wizard.source_row_count, 2)
        self.assertEqual(wizard.preview_ids.mapped("status"), ["resolved", "resolved"])
        self.assertEqual(self.env["product.product"].search_count([]), before["products"])
        self.assertEqual(self.env["product.supplierinfo"].search_count([]), before["supplierinfos"])
        self.assertEqual(order.order_line.ids, before["lines"])

        wizard.action_apply()

        self.assertEqual(order.origin, "HEADER-MUST-STAY")
        self.assertEqual(order.order_line.mapped("product_id"), self.product_a | self.product_b)
        self.assertEqual(order.order_line.mapped("product_qty"), [2, 3])
        self.assertEqual(order.order_line.mapped("price_unit"), [12.5, 8.25])
        self.assertEqual(
            order.order_line.mapped("name"),
            ["First imported line", "Second imported line"],
        )
        self.assertEqual(unrelated_tier.price, 77)
        exact_tiers = self.env["product.supplierinfo"].search([
            ("partner_id", "=", self.vendor.commercial_partner_id.id),
            ("product_id", "in", [self.product_a.id, self.product_b.id]),
            ("company_id", "=", self.company.id),
            ("currency_id", "=", order.currency_id.id),
            ("product_uom_id", "=", self.uom.id),
            ("min_qty", "=", 0),
        ])
        self.assertEqual(len(exact_tiers), 2)

        with self.assertRaisesRegex(UserError, "empty order"):
            wizard.action_preview()
        with self.assertRaisesRegex(UserError, "empty order"):
            wizard.action_apply()
        self.assertEqual(len(order.order_line), 2)
        self.assertEqual(len(exact_tiers.exists()), 2)

    def test_supplier_code_precedes_fallback_and_updates_exact_tier(self):
        order = self._new_order()
        supplierinfo = self.env["product.supplierinfo"].create({
            "partner_id": self.vendor.commercial_partner_id.id,
            "product_id": self.product_a.id,
            "product_tmpl_id": self.product_a.product_tmpl_id.id,
            "company_id": self.company.id,
            "currency_id": order.currency_id.id,
            "product_uom_id": self.uom.id,
            "product_code": "VENDOR-A",
            "min_qty": 0,
            "price": 2,
        })
        wizard = self._new_wizard(
            order,
            "Vendor Code,Code,Barcode,Qty,Price\n"
            "VENDOR-A,IMP-B,9900000000012,1,19.75\n",
        )
        self._map(wizard, {
            "Vendor Code": "supplier_code",
            "Code": "default_code",
            "Barcode": "barcode",
            "Qty": "quantity",
            "Price": "price",
        })
        wizard.action_preview()
        self.assertEqual(wizard.preview_ids.product_id, self.product_a)

        wizard.action_apply()

        self.assertEqual(order.order_line.product_id, self.product_a)
        self.assertEqual(supplierinfo.price, 19.75)

    def test_mapping_layout_empty_size_stale_and_price_conflicts(self):
        order = self._new_order()
        empty = self._new_wizard(order, " \n")
        with self.assertRaisesRegex(UserError, "no content"):
            empty.action_parse()
        unsupported = self._new_wizard(order, "Code,Qty,Price\nIMP-A,1,1\n")
        unsupported.file_name = "purchase.ods"
        with self.assertRaisesRegex(UserError, "Only CSV and XLSX"):
            unsupported.action_parse()
        invalid_layout = self._new_wizard(
            order, "Intro\nCode,Qty,Price\n", header_row=2, data_row=3
        )
        with self.assertRaisesRegex(UserError, "data range"):
            invalid_layout.action_parse()
        oversized = self._new_wizard(order, "Code,Qty,Price\nIMP-A,1,1\n")
        oversized.max_file_size_mb = 1
        oversized.file_data = base64.b64encode(b"x" * (1024 * 1024 + 1))
        with self.assertRaisesRegex(UserError, "size limit"):
            oversized.action_parse()
        too_many = self._new_wizard(
            order, "Code,Qty,Price\nIMP-A,1,1\nIMP-B,1,1\n", max_rows=1
        )
        with self.assertRaisesRegex(UserError, "row limit"):
            too_many.action_parse()

        incomplete = self._new_wizard(order, "Code,Qty,Price\nIMP-A,1,1\n")
        self._map(incomplete, {"Code": "default_code", "Qty": "quantity"})
        with self.assertRaisesRegex(UserError, "Quantity and unit price"):
            incomplete.action_preview()
        duplicate = self._new_wizard(order, "Code,Qty,Other Qty,Price\nIMP-A,1,2,1\n")
        self._map(duplicate, {
            "Code": "default_code",
            "Qty": "quantity",
            "Other Qty": "quantity",
            "Price": "price",
        })
        with self.assertRaisesRegex(UserError, "only be mapped once"):
            duplicate.action_preview()

        wizard = self._new_wizard(
            order,
            "Code,Qty,Price\nIMP-A,1,10\nIMP-A,2,11\n",
        )
        self._map(wizard, {
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        })
        wizard.action_preview()
        self.assertFalse(wizard.preview_valid)
        self.assertEqual(wizard.error_count, 2)
        self.assertIn("conflicting prices", wizard.preview_ids[0].error_message)

        wizard.file_data = base64.b64encode(
            b"Code,Qty,Price\nIMP-A,1,10\n"
        )
        wizard.action_preview()
        self.assertTrue(wizard.preview_valid)
        order.order_line = [Command.create({
            "product_id": self.product_b.id,
            "product_qty": 1,
            "product_uom_id": self.uom.id,
            "price_unit": 1,
        })]
        existing_line = order.order_line
        with self.assertRaisesRegex(UserError, "empty order"):
            wizard.action_apply()
        self.assertEqual(order.order_line, existing_line)

        stale_order = self._new_order()
        stale = self._new_wizard(
            stale_order,
            "Code,Qty,Price\nIMP-A,1,10\n",
        )
        self._map(stale, {
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        })
        stale.action_preview()
        stale.separator = ";"
        with self.assertRaisesRegex(UserError, "Validate the import"):
            stale.action_apply()

    def test_nonempty_order_rejects_all_import_entry_points(self):
        csv_content = "Code,Qty,Price\nIMP-A,1,10\n"
        targets = {
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        }
        for line_kind in ("product", "section", "note"):
            for entry_point in ("open", "parse", "preview", "apply"):
                with self.subTest(line_kind=line_kind, entry_point=entry_point):
                    order = self._new_order()
                    wizard = False
                    if entry_point != "open":
                        wizard = self._new_wizard(order, csv_content)
                    if entry_point in ("preview", "apply"):
                        self._map(wizard, targets)
                    if entry_point == "apply":
                        wizard.action_preview()
                    line_values = {
                        "order_id": order.id,
                        "product_qty": 0,
                    }
                    if line_kind == "product":
                        line_values.update({
                            "product_id": self.product_b.id,
                            "product_qty": 1,
                            "product_uom_id": self.uom.id,
                            "price_unit": 1,
                        })
                    else:
                        line_values.update({
                            "display_type": f"line_{line_kind}",
                            "name": f"Existing {line_kind}",
                        })
                    existing_line = self.env["purchase.order.line"].create(line_values)
                    product_count = self.env["product.product"].search_count([])
                    supplierinfo_count = self.env["product.supplierinfo"].search_count([])

                    with self.assertRaisesRegex(UserError, "empty order"):
                        if entry_point == "open":
                            order.with_user(self.import_user).action_open_line_import()
                        else:
                            getattr(wizard, f"action_{entry_point}")()

                    self.assertEqual(order.order_line, existing_line)
                    self.assertEqual(
                        self.env["product.product"].search_count([]), product_count
                    )
                    self.assertEqual(
                        self.env["product.supplierinfo"].search_count([]),
                        supplierinfo_count,
                    )

    def test_standalone_creation_uses_profile_defaults_and_rolls_back_failure(self):
        order = self._new_order()
        csv_content = "Name,Code,Barcode,Qty,Price\nNew Import Product,NEW-01,9900000000098,2,6.5\n"
        wizard = self._new_wizard(
            order,
            csv_content,
            unmatched_policy="create",
            creation_mode="standalone",
            default_product_type="consu",
            default_is_storable=True,
            default_tracking="lot",
            default_uom_id=self.uom.id,
            default_purchase_uom_id=self.uom.id,
            default_purchase_ok=True,
            default_sale_ok=False,
        )
        self._map(wizard, {
            "Name": "product_name",
            "Code": "default_code",
            "Barcode": "barcode",
            "Qty": "quantity",
            "Price": "price",
        })
        wizard.action_preview()
        self.assertEqual(wizard.preview_ids.status, "create")
        self.assertFalse(self.env["product.product"].search([("default_code", "=", "NEW-01")]))
        self.assertFalse(order.order_line)
        product_count = self.env["product.product"].search_count([])
        supplierinfo_count = self.env["product.supplierinfo"].search_count([])
        wizard_class = type(wizard)
        original_upsert = wizard_class._upsert_supplierinfos

        def _failing_upsert(record, normalized_products):
            original_upsert(record, normalized_products)
            raise UserError("Forced rollback")

        with self.assertRaisesRegex(UserError, "Forced rollback"):
            with self.cr.savepoint():
                with patch.object(wizard_class, "_upsert_supplierinfos", _failing_upsert):
                    wizard.action_apply()
        self.env.invalidate_all()
        self.assertEqual(self.env["product.product"].search_count([]), product_count)
        self.assertEqual(
            self.env["product.supplierinfo"].search_count([]), supplierinfo_count
        )
        self.assertFalse(order.order_line)
        self.assertFalse(self.env["product.product"].search([("default_code", "=", "NEW-01")]))

        wizard.action_preview()
        wizard.action_apply()
        product = order.order_line.product_id
        self.assertEqual(product.name, "New Import Product")
        self.assertEqual(product.default_code, "NEW-01")
        self.assertEqual(product.barcode, "9900000000098")
        self.assertTrue(product.is_storable)
        self.assertEqual(product.tracking, "lot")
        self.assertFalse(product.sale_ok)
        with self.assertRaisesRegex(UserError, "empty order"):
            wizard.action_apply()

    def test_ambiguity_unmatched_and_duplicate_existing_supplier_price(self):
        duplicate_product = self.env["product.product"].create({
            "name": "Import Duplicate Reference",
            "default_code": "IMP-A",
            "purchase_ok": True,
            "company_id": self.company.id,
        })
        order = self._new_order()
        ambiguous = self._new_wizard(
            order,
            "Name,Code,Qty,Price\nMust Not Be Created,IMP-A,1,2\n",
            unmatched_policy="create",
        )
        self._map(ambiguous, {
            "Name": "product_name",
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        })
        ambiguous.action_preview()
        self.assertFalse(ambiguous.preview_valid)
        self.assertIn("ambiguous", ambiguous.preview_ids.error_message)
        self.assertFalse(ambiguous.preview_ids.product_id)
        self.assertFalse(
            self.env["product.product"].search([("name", "=", "Must Not Be Created")])
        )
        duplicate_product.default_code = "IMP-DUPLICATE-ONLY"

        unmatched = self._new_wizard(order, "Code,Qty,Price\nNO-MATCH,1,2\n")
        self._map(unmatched, {
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        })
        unmatched.action_preview()
        self.assertFalse(unmatched.preview_valid)
        self.assertIn("No product matches", unmatched.preview_ids.error_message)

        supplier_values = {
            "partner_id": self.vendor.commercial_partner_id.id,
            "product_id": self.product_b.id,
            "product_tmpl_id": self.product_b.product_tmpl_id.id,
            "company_id": self.company.id,
            "currency_id": order.currency_id.id,
            "product_uom_id": self.uom.id,
            "min_qty": 0,
            "price": 1,
        }
        self.env["product.supplierinfo"].create([supplier_values, supplier_values])
        duplicate_price = self._new_wizard(
            order, "Code,Qty,Price\nIMP-B,1,2\n"
        )
        self._map(duplicate_price, {
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        })
        duplicate_price.action_preview()
        self.assertFalse(duplicate_price.preview_valid)
        self.assertIn("Multiple supplier prices", duplicate_price.preview_ids.error_message)

    def test_dynamic_variant_creation_reuses_catalog_and_rejects_bad_combination(self):
        attribute = self.env["product.attribute"].create({
            "name": "Import Color",
            "create_variant": "dynamic",
        })
        red, blue = self.env["product.attribute.value"].create([
            {"name": "Import Red", "attribute_id": attribute.id},
            {"name": "Import Blue", "attribute_id": attribute.id},
        ])
        template = self.env["product.template"].create({
            "name": "Import Dynamic Template",
            "purchase_ok": True,
            "company_id": self.company.id,
            "attribute_line_ids": [Command.create({
                "attribute_id": attribute.id,
                "value_ids": [Command.set([red.id, blue.id])],
            })],
        })
        line_count = len(template.attribute_line_ids)
        value_count = len(template.attribute_line_ids.value_ids)
        order = self._new_order()
        wizard = self._new_wizard(
            order,
            "Color,Code,Qty,Price\nImport Red,DYN-RED,1,4\n",
            unmatched_policy="create",
            creation_mode="variant",
            variant_template_id=template.id,
            default_purchase_uom_id=self.uom.id,
        )
        self._map(wizard, {
            "Color": ("attribute", attribute),
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        })
        wizard.action_preview()
        self.assertEqual(wizard.preview_ids.status, "create")
        wizard.action_apply()
        variant = order.order_line.product_id
        self.assertEqual(variant.product_tmpl_id, template)
        self.assertEqual(variant.default_code, "DYN-RED")
        self.assertEqual(len(template.attribute_line_ids), line_count)
        self.assertEqual(len(template.attribute_line_ids.value_ids), value_count)

        reuse = self._new_wizard(
            self._new_order(),
            "Color,Qty,Price\nImport Red,2,5\n",
            unmatched_policy="create",
            creation_mode="variant",
            variant_template_id=template.id,
        )
        self._map(reuse, {
            "Color": ("attribute", attribute),
            "Qty": "quantity",
            "Price": "price",
        })
        reuse.action_preview()
        self.assertEqual(reuse.preview_ids.status, "resolved")
        self.assertEqual(reuse.preview_ids.product_id, variant)

        bad = self._new_wizard(
            self._new_order(),
            "Color,Qty,Price\nMissing Value,1,5\n",
            unmatched_policy="create",
            creation_mode="variant",
            variant_template_id=template.id,
        )
        self._map(bad, {
            "Color": ("attribute", attribute),
            "Qty": "quantity",
            "Price": "price",
        })
        bad.action_preview()
        self.assertFalse(bad.preview_valid)
        self.assertIn("missing or ambiguous", bad.preview_ids.error_message)

    def test_xlsx_worksheet_and_rows(self):
        if importlib.util.find_spec("openpyxl") is None:
            self.skipTest("openpyxl is not installed")
        from openpyxl import Workbook

        workbook = Workbook()
        workbook.active.title = "Ignore"
        sheet = workbook.create_sheet("Lines")
        sheet.append(["Intro"])
        sheet.append(["Code", "Qty", "Price"])
        sheet.append(["IMP-B", 4, 9.5])
        stream = BytesIO()
        workbook.save(stream)
        order = self._new_order()
        wizard = self.env["purchase.order.line.import.wizard"].with_user(
            self.import_user
        ).create({
            "order_id": order.id,
            "file_data": base64.b64encode(stream.getvalue()),
            "file_name": "purchase.xlsx",
            "sheet": "Lines",
            "header_row": 2,
            "data_row": 3,
        })
        self._map(wizard, {
            "Code": "default_code",
            "Qty": "quantity",
            "Price": "price",
        })
        self.assertIn("Lines", wizard.available_sheets)
        wizard.action_preview()
        self.assertTrue(wizard.preview_valid)
        self.assertEqual(wizard.preview_ids.product_id, self.product_b)

    def test_xlsx_merged_header_ignores_empty_physical_columns(self):
        fixture = Path(__file__).with_name(
            "№ 4649 від 25 червня 2026 р-2..xlsx"
        )
        wizard = self.env["purchase.order.line.import.wizard"].with_user(
            self.import_user
        ).create({
            "order_id": self._new_order().id,
            "file_data": base64.b64encode(fixture.read_bytes()),
            "file_name": fixture.name,
            "header_row": 14,
            "data_row": 16,
        })

        wizard.action_parse()

        self.assertEqual(
            wizard.mapping_ids.mapped("source_column"),
            ["№", "Артикул", "Товар", "Кількість", "Ціна без ПДВ", "Сума без ПДВ"],
        )
        for mapping in wizard.mapping_ids:
            mapping.target = {
                "Артикул": "default_code",
                "Кількість": "quantity",
                "Ціна без ПДВ": "price",
            }.get(mapping.source_column)

        normalized_rows = wizard._validate_rows(wizard._parse_file())

        self.assertEqual(
            [row["source_row"] for row in normalized_rows],
            [16, 17, 18, 19],
        )

    def test_standard_purchase_confirmation_is_unchanged(self):
        order = self._new_order()
        self.env["purchase.order.line"].create({
            "order_id": order.id,
            "product_id": self.product_a.id,
            "product_qty": 1,
            "product_uom_id": self.uom.id,
            "price_unit": 3,
        })

        order.button_confirm()

        self.assertIn(order.state, ("purchase", "to approve"))
        if order.state == "purchase":
            self.assertTrue(order.picking_ids)
            order.picking_ids.move_ids.quantity = 1
            order.picking_ids.with_context(skip_backorder=True).button_validate()
            self.assertEqual(order.picking_ids.state, "done")
            invoice_action = order.action_create_invoice()
            invoice = self.env["account.move"].browse(invoice_action["res_id"])
            self.assertEqual(invoice.move_type, "in_invoice")
            self.assertEqual(invoice.invoice_line_ids.purchase_line_id, order.order_line)

        cancelled_order = self._new_order()
        cancelled_order.button_cancel()
        self.assertEqual(cancelled_order.state, "cancel")
