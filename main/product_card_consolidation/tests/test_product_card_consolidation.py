import base64
from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "product_card_consolidation")
class TestProductCardConsolidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = cls.env.ref(
            "product_card_consolidation.group_product_consolidation_manager"
        )
        cls.product_manager_group = cls.env.ref("product.group_product_manager")
        cls.env.user.group_ids = [Command.link(cls.group.id)]
        cls.ProductTemplate = cls.env["product.template"]
        cls.Service = cls.env["product.card.consolidation.service"]
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.fifo_category = cls.env["product.category"].create({
            "name": "Product consolidation FIFO",
            "property_cost_method": "fifo",
            "property_valuation": "periodic",
        })

    def test_consolidation_permission_is_a_separate_privilege(self):
        self.assertNotEqual(
            self.group.privilege_id,
            self.product_manager_group.privilege_id,
        )
        self.assertNotIn(self.product_manager_group, self.group.all_implied_ids)

    def _products(self, **duplicate_values):
        common = {
            "type": "consu",
            "is_storable": False,
            "company_id": self.env.company.id,
        }
        canonical = self.ProductTemplate.create({
            **common,
            "name": "Canonical product",
            "default_code": "CANONICAL",
            "barcode": "1000000000016",
        })
        duplicate = self.ProductTemplate.create({
            **common,
            "name": "Duplicate product",
            "default_code": "FORMER-CODE",
            "barcode": "1000000000023",
            **duplicate_values,
        })
        return canonical, duplicate

    def _stock_products(self):
        common = {
            "type": "consu",
            "is_storable": True,
            "company_id": self.env.company.id,
            "categ_id": self.fifo_category.id,
        }
        canonical, duplicate = self.ProductTemplate.create([
            {
                **common,
                "name": "Canonical stocked product",
                "default_code": "CANONICAL-STOCK",
            },
            {
                **common,
                "name": "Duplicate stocked product",
                "default_code": "DUPLICATE-STOCK",
            },
        ])
        return canonical, duplicate

    def _make_stock_move(
        self,
        product,
        quantity,
        location,
        location_dest,
        *,
        unit_cost=None,
        package=None,
        date=None,
        purchase_line=None,
    ):
        values = {
            "product_id": product.id,
            "product_uom": product.uom_id.id,
            "product_uom_qty": quantity,
            "company_id": self.env.company.id,
            "location_id": location.id,
            "location_dest_id": location_dest.id,
        }
        if unit_cost is not None:
            values.update({
                "price_unit": unit_cost,
                "value_manual": quantity * unit_cost,
            })
        if purchase_line:
            values["purchase_line_id"] = purchase_line.id
        move = self.env["stock.move"].create(values)
        move._action_confirm()
        move._action_assign()
        if package:
            if location_dest.is_valued_internal:
                move.move_line_ids.result_package_id = package
            else:
                move.move_line_ids.package_id = package
        move.picked = True
        move._action_done()
        if date:
            move.date = date
        return move

    def _receive(self, product, quantity, unit_cost, **kwargs):
        return self._make_stock_move(
            product,
            quantity,
            self.supplier_location,
            kwargs.pop("location", self.stock_location),
            unit_cost=unit_cost,
            **kwargs,
        )

    def _deliver(self, product, quantity, **kwargs):
        return self._make_stock_move(
            product,
            quantity,
            kwargs.pop("location", self.stock_location),
            self.customer_location,
            **kwargs,
        )

    def test_preview_is_read_only_and_consolidation_resolves_aliases(self):
        canonical, duplicate = self._products()
        source_write_date = duplicate.write_date
        stock_move_count = self.env["stock.move"].search_count([
            ("origin", "=", "Product card consolidation"),
        ])

        analysis = self.Service.analyze(canonical, duplicate)

        self.assertFalse(analysis["blockers"])
        self.assertTrue(duplicate.active)
        self.assertFalse(duplicate.merged_into_id)
        self.assertEqual(duplicate.write_date, source_write_date)

        self.Service.consolidate(canonical, duplicate)

        self.assertFalse(duplicate.active)
        self.assertEqual(duplicate.merged_into_id, canonical)
        self.assertEqual(canonical.name, "Canonical product")
        self.assertEqual(canonical.default_code, "CANONICAL")
        history_action = canonical.action_open_merged_sources()
        self.assertEqual(history_action["domain"], [("merged_into_id", "=", canonical.id)])
        resolved = self.env["product.product"]._resolve_identifier_batch(
            "default_code", {"FORMER-CODE"}, self.env.company
        )
        self.assertEqual(resolved["FORMER-CODE"], canonical.product_variant_id)
        audit_messages = canonical.message_ids.filtered(
            lambda message: "Duplicate product" in (message.body or "")
        )
        self.assertEqual(len(audit_messages), 1)
        with self.assertRaises(ValidationError):
            duplicate.action_unarchive()
        with self.assertRaises(UserError):
            self.Service.consolidate(canonical, duplicate)

        another_duplicate = self.ProductTemplate.create({
            "name": "Another duplicate",
            "default_code": "ANOTHER-FORMER-CODE",
            "type": "consu",
            "is_storable": False,
            "company_id": self.env.company.id,
        })
        self.Service.consolidate(canonical, another_duplicate)
        self.assertEqual(len(canonical.merged_source_ids), 2)
        self.assertEqual(len(canonical.product_variant_id.alias_ids), 3)
        self.assertEqual(
            self.env["stock.move"].search_count([
                ("origin", "=", "Product card consolidation"),
            ]),
            stock_move_count,
        )

    def test_draft_lines_move_and_confirmed_history_stays(self):
        canonical, duplicate = self._products()
        partner = self.env["res.partner"].create({"name": "Consolidation partner"})
        quotation = self.env["sale.order"].create({"partner_id": partner.id})
        draft_line = self.env["sale.order.line"].create({
            "order_id": quotation.id,
            "product_id": duplicate.product_variant_id.id,
            "product_uom_qty": 2,
            "price_unit": 17,
            "name": "Entered description",
        })
        confirmed = self.env["sale.order"].create({"partner_id": partner.id})
        history_line = self.env["sale.order.line"].create({
            "order_id": confirmed.id,
            "product_id": duplicate.product_variant_id.id,
            "product_uom_qty": 1,
            "price_unit": 23,
        })
        duplicate_variant = duplicate.product_variant_id
        confirmed.action_confirm()
        confirmed.picking_ids.action_cancel()

        self.Service.consolidate(canonical, duplicate)

        self.assertEqual(draft_line.product_id, canonical.product_variant_id)
        self.assertEqual(draft_line.name, "Entered description")
        self.assertEqual(draft_line.price_unit, 17)
        self.assertEqual(history_line.product_id, duplicate_variant)

    def test_alias_crud_is_service_only(self):
        canonical, duplicate = self._products()
        values = {
            "product_id": canonical.product_variant_id.id,
            "source_product_id": duplicate.product_variant_id.id,
            "identifier_type": "default_code",
            "value": "OTHER-CODE",
            "company_id": self.env.company.id,
        }
        with self.assertRaises(AccessError):
            self.env["product.identifier.alias"].create(values)

    def test_identifier_conflict_blocks_preview(self):
        canonical, duplicate = self._products()
        self.ProductTemplate.create({
            "name": "Conflicting product",
            "default_code": duplicate.default_code,
            "type": "consu",
            "company_id": self.env.company.id,
        })

        analysis = self.Service.analyze(canonical, duplicate)

        self.assertTrue(
            any(line["category"] == "identifiers" for line in analysis["blockers"])
        )

    def test_unauthorized_api_is_denied(self):
        canonical, duplicate = self._products()
        user = self.env["res.users"].create({
            "name": "Ordinary product user",
            "login": "ordinary-product-user",
            "group_ids": [Command.link(self.env.ref("base.group_user").id)],
        })

        with self.assertRaises(AccessError):
            self.Service.with_user(user).analyze(canonical, duplicate)

    def test_cross_company_api_is_denied(self):
        other_company = self.env["res.company"].create({"name": "Denied company"})
        templates = self.ProductTemplate.with_context(
            allowed_company_ids=(self.env.company | other_company).ids
        ).with_company(other_company).create([
            {"name": "Denied canonical", "company_id": other_company.id},
            {"name": "Denied duplicate", "company_id": other_company.id},
        ])
        user = self.env["res.users"].create({
            "name": "Restricted consolidation manager",
            "login": "restricted-consolidation-manager",
            "company_id": self.env.company.id,
            "company_ids": [Command.set(self.env.company.ids)],
            "group_ids": [Command.link(self.group.id)],
        })

        with self.assertRaises(AccessError):
            self.Service.with_user(user).analyze(templates[0], templates[1])

    def test_stock_and_tracking_blockers(self):
        canonical, duplicate = self._products(tracking="lot")

        analysis = self.Service.analyze(canonical, duplicate)

        self.assertTrue(
            any(line["category"] == "tracking" for line in analysis["blockers"])
        )

    def test_failure_after_handlers_rolls_back_at_transaction_boundary(self):
        canonical, duplicate = self._products()
        partner = self.env["res.partner"].create({"name": "Rollback partner"})
        quotation = self.env["sale.order"].create({"partner_id": partner.id})
        line = self.env["sale.order.line"].create({
            "order_id": quotation.id,
            "product_id": duplicate.product_variant_id.id,
            "product_uom_qty": 1,
        })

        def fail_after_handlers(_service, _canonical, _duplicate):
            raise UserError("Forced consolidation failure")

        service_type = type(self.Service)
        with self.assertRaises(UserError), self.env.cr.savepoint(), patch.object(
            service_type,
            "_consolidation_after_handlers_hook",
            fail_after_handlers,
        ):
            self.Service.consolidate(canonical, duplicate)

        self.assertEqual(line.product_id, duplicate.product_variant_id)
        self.assertTrue(duplicate.active)
        self.assertFalse(duplicate.merged_into_id)
        self.assertFalse(canonical.product_variant_id.alias_ids)

        self.Service.consolidate(canonical, duplicate)
        self.assertEqual(duplicate.merged_into_id, canonical)

    def test_wizard_selection_cancellation_and_stale_confirmation(self):
        canonical, duplicate = self._products()
        Wizard = self.env["product.consolidation.wizard"]
        invalid = Wizard.create({
            "product_template_ids": [Command.set(canonical.ids)],
            "canonical_template_id": canonical.id,
        })
        with self.assertRaises(UserError):
            invalid.action_preview()

        wizard = Wizard.create({
            "product_template_ids": [Command.set((canonical | duplicate).ids)],
            "canonical_template_id": canonical.id,
        })
        wizard.action_preview()
        self.assertFalse(wizard.has_blockers)
        self.assertTrue(any(
            line.category == "canonical_values" for line in wizard.preview_line_ids
        ))
        self.assertTrue(canonical.active and duplicate.active)

        wizard.action_request_confirmation()
        duplicate.tracking = "lot"
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertTrue(duplicate.active)
        self.assertFalse(duplicate.merged_into_id)

    def test_compatibility_stock_lot_and_inventory_blockers(self):
        canonical, duplicate = self._products(is_storable=True)
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("product_type", categories)

        canonical.is_storable = True
        different_uom = self.env["uom.uom"].create({
            "name": "Consolidation test dozen",
            "relative_uom_id": canonical.uom_id.id,
            "relative_factor": 12,
        })
        duplicate.uom_id = different_uom
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("uom", categories)
        duplicate.uom_id = canonical.uom_id

        duplicate.tracking = "lot"
        self.env["stock.lot"].create({
            "name": "CONSOLIDATION-LOT",
            "product_id": duplicate.product_variant_id.id,
        })
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("tracking", categories)

        duplicate.tracking = "none"
        quant = self.env["stock.quant"].create({
            "product_id": duplicate.product_variant_id.id,
            "location_id": self.env.ref("stock.stock_location_stock").id,
            "quantity": 1,
        })
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("valuation", categories)
        quant.write({"quantity": 0, "inventory_quantity": 2})
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("inventory_count", categories)

    def test_stock_transfer_preserves_quantity_fifo_value_and_audit(self):
        canonical, duplicate = self._stock_products()
        original_date = fields.Datetime.now() - timedelta(days=30)
        canonical_receipt = self._receive(
            canonical.product_variant_id, 5, 2, date=original_date
        )
        source_receipts = self.env["stock.move"]
        source_receipts |= self._receive(
            duplicate.product_variant_id, 4, 3, date=original_date + timedelta(days=1)
        )
        source_receipts |= self._receive(
            duplicate.product_variant_id, 6, 5, date=original_date + timedelta(days=2)
        )
        source_snapshot = {
            move.id: (move.product_id, move.date, move.value)
            for move in source_receipts | canonical_receipt
        }
        before = fields.Datetime.now()
        analysis = self.Service.analyze(canonical, duplicate)

        self.assertFalse(analysis["blockers"])
        total = next(
            line for line in analysis["lines"]
            if line["category"] == "stock_transfer"
        )
        self.assertEqual(total["quantity"], 10)
        self.assertEqual(total["value"], 42)

        self.Service.consolidate(canonical, duplicate)

        company = self.env.company
        self.assertEqual(
            self.Service._stock_quantity(canonical.product_variant_id, company),
            15,
        )
        self.assertEqual(
            self.Service._stock_quantity(duplicate.product_variant_id, company),
            0,
        )
        self.assertFalse(duplicate.active)
        canonical.product_variant_id.invalidate_recordset()
        duplicate.product_variant_id.invalidate_recordset()
        self.assertEqual(
            canonical.product_variant_id.total_value
            + duplicate.product_variant_id.total_value,
            52,
        )
        incoming = self.env["stock.move"].search([
            ("product_id", "=", canonical.product_variant_id.id),
            ("consolidation_source_receipt_id", "!=", False),
        ], order="id")
        self.assertEqual(len(incoming), 2)
        self.assertEqual(incoming.mapped("value"), [12, 30])
        self.assertEqual(incoming.mapped("quantity"), [4, 6])
        self.assertEqual(incoming.consolidation_source_receipt_id, source_receipts)
        self.assertEqual(
            incoming.mapped("consolidation_source_date"),
            source_receipts.mapped("date"),
        )
        self.assertTrue(all(move.date >= before for move in incoming))
        self.assertTrue(all(move.consolidation_out_move_id.state == "done" for move in incoming))
        self.assertTrue(all(move.date >= before for move in incoming.consolidation_out_move_id))
        remaining_moves = list(
            canonical.product_variant_id._get_remaining_moves()[
                canonical.product_variant_id
            ]
        )
        self.assertEqual(remaining_moves[0], canonical_receipt)
        self.assertEqual(remaining_moves[-2:], list(incoming))
        for move_id, snapshot in source_snapshot.items():
            move = self.env["stock.move"].browse(move_id)
            self.assertEqual((move.product_id, move.date, move.value), snapshot)
        audit_messages = canonical.message_ids.filtered(
            lambda message: "model=stock.move" in (message.body or "")
        )
        self.assertEqual(len(audit_messages), 1)

    def test_stock_transfer_preserves_partial_layers_locations_and_packages(self):
        canonical, duplicate = self._stock_products()
        secondary_location = self.env["stock.location"].create({
            "name": "Consolidation secondary location",
            "usage": "internal",
            "location_id": self.stock_location.location_id.id,
            "company_id": self.env.company.id,
        })
        package = self.env["stock.package"].create({
            "name": "CONSOLIDATION-PACKAGE",
        })
        first_receipt = self._receive(duplicate.product_variant_id, 8, 2)
        second_receipt = self._receive(
            duplicate.product_variant_id,
            5,
            4,
            location=secondary_location,
            package=package,
        )
        self._deliver(duplicate.product_variant_id, 3)
        quants_before = self.Service._internal_quants(
            duplicate.product_variant_id, self.env.company
        ).filtered(lambda quant: quant.quantity > 0)
        bucket_before = sorted(
            (quant.location_id.id, quant.package_id.id, quant.quantity)
            for quant in quants_before
        )

        analysis = self.Service.analyze(canonical, duplicate)

        self.assertFalse(analysis["blockers"])
        by_source = {}
        for segment in analysis["stock_plan"]:
            quantity, value = by_source.get(segment["source_move_id"], (0, 0))
            by_source[segment["source_move_id"]] = (
                quantity + segment["quantity"],
                value + segment["value"],
            )
        self.assertEqual(by_source[first_receipt.id], (5, 10))
        self.assertEqual(by_source[second_receipt.id], (5, 20))

        self.Service.consolidate(canonical, duplicate)

        canonical_quants = self.Service._internal_quants(
            canonical.product_variant_id, self.env.company
        ).filtered(lambda quant: quant.quantity > 0)
        bucket_after = sorted(
            (quant.location_id.id, quant.package_id.id, quant.quantity)
            for quant in canonical_quants
        )
        self.assertEqual(bucket_after, bucket_before)
        incoming = self.env["stock.move"].search([
            ("product_id", "=", canonical.product_variant_id.id),
            ("consolidation_source_receipt_id", "!=", False),
        ])
        self.assertEqual(sum(incoming.mapped("quantity")), 10)
        self.assertEqual(sum(incoming.mapped("value")), 30)

    def test_stock_preview_staleness_and_cancellation_create_no_movements(self):
        canonical, duplicate = self._stock_products()
        self._receive(duplicate.product_variant_id, 2, 7)
        Wizard = self.env["product.consolidation.wizard"]
        wizard = Wizard.create({
            "product_template_ids": [Command.set((canonical | duplicate).ids)],
            "canonical_template_id": canonical.id,
        })
        move_count = self.env["stock.move"].search_count([
            ("origin", "=", "Product card consolidation"),
        ])

        wizard.action_request_confirmation()

        self.assertEqual(
            self.env["stock.move"].search_count([
                ("origin", "=", "Product card consolidation"),
            ]),
            move_count,
        )
        self._deliver(duplicate.product_variant_id, 1)
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertTrue(duplicate.active)
        self.assertFalse(duplicate.merged_into_id)
        self.assertEqual(
            self.env["stock.move"].search_count([
                ("origin", "=", "Product card consolidation"),
            ]),
            move_count,
        )

    def test_stock_transfer_rejects_a_concurrent_quant_lock(self):
        canonical, duplicate = self._stock_products()
        self._receive(duplicate.product_variant_id, 2, 7)
        QuantClass = type(self.env["stock.quant"])

        with patch.object(
            QuantClass,
            "try_lock_for_update",
            return_value=self.env["stock.quant"],
        ), self.assertRaises(UserError):
            self.Service.consolidate(canonical, duplicate)

        self.assertEqual(
            self.Service._stock_quantity(duplicate.product_variant_id, self.env.company),
            2,
        )
        self.assertFalse(self.env["stock.move"].search([
            ("origin", "=", "Product card consolidation"),
        ]))
        self.assertTrue(duplicate.active)

    def test_stock_transfer_failure_rolls_back_and_retry_succeeds(self):
        canonical, duplicate = self._stock_products()
        self._receive(duplicate.product_variant_id, 2, 7)

        def fail_after_handlers(_service, _canonical, _duplicate):
            raise UserError("Forced consolidation failure")

        service_type = type(self.Service)
        with self.assertRaises(UserError), self.env.cr.savepoint(), patch.object(
            service_type,
            "_consolidation_after_handlers_hook",
            fail_after_handlers,
        ):
            self.Service.consolidate(canonical, duplicate)

        self.assertEqual(
            self.Service._stock_quantity(canonical.product_variant_id, self.env.company),
            0,
        )
        self.assertEqual(
            self.Service._stock_quantity(duplicate.product_variant_id, self.env.company),
            2,
        )
        self.assertFalse(self.env["stock.move"].search([
            ("origin", "=", "Product card consolidation"),
        ]))
        self.assertTrue(duplicate.active)

        self.Service.consolidate(canonical, duplicate)

        self.assertEqual(
            self.Service._stock_quantity(canonical.product_variant_id, self.env.company),
            2,
        )
        self.assertFalse(duplicate.active)

    def test_stock_transfer_blockers_are_reported_separately(self):
        canonical, duplicate = self._stock_products()
        self.env["stock.quant"].create({
            "product_id": duplicate.product_variant_id.id,
            "location_id": self.stock_location.id,
            "quantity": 1,
        })
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("stock_value_reconciliation", categories)

        canonical, duplicate = self._stock_products()
        self.env["stock.quant"].create({
            "product_id": duplicate.product_variant_id.id,
            "location_id": self.stock_location.id,
            "quantity": -1,
        })
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("negative_stock", categories)

        canonical, duplicate = self._stock_products()
        self.env["stock.quant"].create({
            "product_id": duplicate.product_variant_id.id,
            "location_id": self.stock_location.id,
            "quantity": 1,
            "owner_id": self.env.company.partner_id.id,
        })
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("owner", categories)

        canonical, duplicate = self._stock_products()
        self._receive(duplicate.product_variant_id, 1, 3)
        outgoing = self.env["stock.move"].create({
            "product_id": duplicate.product_variant_id.id,
            "product_uom": duplicate.uom_id.id,
            "product_uom_qty": 1,
            "company_id": self.env.company.id,
            "location_id": self.stock_location.id,
            "location_dest_id": self.customer_location.id,
        })
        outgoing._action_confirm()
        outgoing._action_assign()
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("reservation", categories)
        self.assertIn("open_stock_moves", categories)

    def test_stock_transfer_requires_matching_valuation_configuration(self):
        canonical, duplicate = self._stock_products()
        self._receive(duplicate.product_variant_id, 1, 3)
        other_inventory_location = self.env["stock.location"].create({
            "name": "Other consolidation inventory adjustment",
            "usage": "inventory",
            "company_id": self.env.company.id,
        })
        canonical.property_stock_inventory = other_inventory_location

        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }

        self.assertIn("valuation", categories)

    def test_preview_warns_when_supplier_billing_can_change_value(self):
        canonical, duplicate = self._stock_products()
        vendor = self.env["res.partner"].create({"name": "Mutable valuation vendor"})
        order = self.env["purchase.order"].create({"partner_id": vendor.id})
        line = self.env["purchase.order.line"].create({
            "order_id": order.id,
            "product_id": duplicate.product_variant_id.id,
            "product_qty": 2,
            "price_unit": 11,
        })
        order.button_confirm()
        receipt = order.picking_ids.move_ids.filtered(
            lambda move: move.product_id == duplicate.product_variant_id
        )
        receipt.value_manual = 22
        receipt._action_assign()
        receipt.picked = True
        receipt._action_done()
        self.assertFalse(line.product_uom_id.is_zero(line.qty_to_invoice))

        analysis = self.Service.analyze(canonical, duplicate)

        warning = next(
            item for item in analysis["lines"]
            if item["category"] == "mutable_valuation"
        )
        self.assertEqual(warning["severity"], "warning")
        self.assertEqual(warning["quantity"], 2)
        self.assertEqual(warning["value"], 22)

    def test_stock_audit_fields_reject_arbitrary_writes(self):
        canonical, duplicate = self._stock_products()
        receipt = self._receive(duplicate.product_variant_id, 1, 3)
        values = {
            "product_id": canonical.product_variant_id.id,
            "product_uom": canonical.uom_id.id,
            "product_uom_qty": 1,
            "company_id": self.env.company.id,
            "location_id": self.supplier_location.id,
            "location_dest_id": self.stock_location.id,
            "consolidation_source_receipt_id": receipt.id,
        }
        with self.assertRaises(AccessError):
            self.env["stock.move"].create(values)

    def test_company_and_multivariant_blockers(self):
        canonical, duplicate = self._products()
        duplicate.company_id = False
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("company", categories)
        duplicate.company_id = self.env.company

        self.env["product.product"].create({"product_tmpl_id": duplicate.id})
        categories = {
            line["category"]
            for line in self.Service.analyze(canonical, duplicate)["blockers"]
        }
        self.assertIn("variants", categories)

    def test_configuration_union_dedup_and_conflict(self):
        canonical, duplicate = self._products()
        tags = self.env["product.tag"].create([
            {"name": "Canonical tag"},
            {"name": "Duplicate tag"},
        ])
        canonical.product_tag_ids = [Command.link(tags[0].id)]
        duplicate.product_tag_ids = [Command.link(tags[1].id)]
        partner = self.env["res.partner"].create({"name": "Configuration vendor"})
        common = {
            "partner_id": partner.id,
            "product_code": "VENDOR-CODE",
            "product_uom_id": canonical.uom_id.id,
            "min_qty": 1,
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
            "price": 10,
        }
        target = self.env["product.supplierinfo"].create({
            **common,
            "product_tmpl_id": canonical.id,
        })
        source = self.env["product.supplierinfo"].create({
            **common,
            "product_tmpl_id": duplicate.id,
        })

        self.Service.consolidate(canonical, duplicate)

        self.assertEqual(canonical.product_tag_ids, tags)
        self.assertTrue(target.exists())
        self.assertFalse(source.exists())

        canonical.barcode = False
        canonical, duplicate = self._products(
            default_code="CONFLICT-SOURCE", barcode="1000000000030"
        )
        self.env["product.supplierinfo"].create({
            **common,
            "product_tmpl_id": canonical.id,
        })
        self.env["product.supplierinfo"].create({
            **common,
            "product_tmpl_id": duplicate.id,
            "price": 11,
        })
        blockers = self.Service.analyze(canonical, duplicate)["blockers"]
        self.assertTrue(any(line["category"] == "supplierinfo" for line in blockers))

    def test_draft_rfq_moves_and_confirmed_rfq_stays(self):
        canonical, duplicate = self._products()
        partner = self.env["res.partner"].create({"name": "RFQ vendor"})
        draft = self.env["purchase.order"].create({"partner_id": partner.id})
        draft_line = self.env["purchase.order.line"].create({
            "order_id": draft.id,
            "product_id": duplicate.product_variant_id.id,
            "product_qty": 3,
            "price_unit": 19,
        })
        confirmed = self.env["purchase.order"].create({"partner_id": partner.id})
        history_line = self.env["purchase.order.line"].create({
            "order_id": confirmed.id,
            "product_id": duplicate.product_variant_id.id,
            "product_qty": 1,
            "price_unit": 29,
        })
        duplicate_variant = duplicate.product_variant_id
        confirmed.button_confirm()
        confirmed.picking_ids.action_cancel()

        self.Service.consolidate(canonical, duplicate)

        self.assertEqual(draft_line.product_id, canonical.product_variant_id)
        self.assertEqual(draft_line.product_qty, 3)
        self.assertEqual(draft_line.price_unit, 19)
        self.assertEqual(history_line.product_id, duplicate_variant)

    def test_ordinary_product_search_archive_and_unarchive(self):
        ordinary = self.ProductTemplate.create({
            "name": "Ordinary unconsolidated product",
            "default_code": "ORDINARY-CODE",
        })
        matches = self.env["product.product"].name_search("ORDINARY-CODE")
        self.assertIn(ordinary.product_variant_id.id, dict(matches))
        ordinary.action_archive()
        self.assertFalse(ordinary.active)
        ordinary.action_unarchive()
        self.assertTrue(ordinary.active)

    def test_ordinary_stock_movement_has_no_consolidation_audit(self):
        canonical, _duplicate = self._stock_products()

        receipt = self._receive(canonical.product_variant_id, 3, 5)

        self.assertEqual(receipt.state, "done")
        self.assertFalse(receipt.consolidation_source_receipt_id)
        self.assertFalse(receipt.consolidation_source_date)
        self.assertFalse(receipt.consolidation_out_move_id)
        self.assertEqual(
            self.Service._stock_quantity(canonical.product_variant_id, self.env.company),
            3,
        )

    def test_installation_metadata_is_empty_for_ordinary_products(self):
        ordinary = self.ProductTemplate.create({"name": "Upgrade-safe product"})

        self.assertFalse(ordinary.merged_into_id)
        self.assertFalse(ordinary.merged_source_ids)
        self.assertFalse(ordinary.product_variant_id.alias_ids)

    def test_former_identifiers_resolve_in_backend_and_purchase_import(self):
        canonical, duplicate = self._products(
            default_code=" FORMER-NORMALIZED ", barcode="1000000000047"
        )
        vendor = self.env["res.partner"].create({"name": "Alias import vendor"})
        supplierinfo = self.env["product.supplierinfo"].create({
            "partner_id": vendor.id,
            "product_id": duplicate.product_variant_id.id,
            "product_tmpl_id": duplicate.id,
            "product_code": "FORMER-SUPPLIER",
            "product_uom_id": duplicate.uom_id.id,
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
            "price": 4,
        })
        self.Service.consolidate(canonical, duplicate)

        alias = canonical.product_variant_id.alias_ids.filtered(
            lambda item: item.identifier_type == "default_code"
        )
        self.assertEqual(alias.value, "FORMER-NORMALIZED")
        self.assertEqual(alias.source_product_id, duplicate.product_variant_id)
        backend_matches = self.env["product.product"].name_search(
            "FORMER-NORMALIZED"
        )
        self.assertIn(canonical.product_variant_id.id, dict(backend_matches))
        other_company = self.env["res.company"].create({"name": "Alias other company"})
        scoped = self.env["product.product"]._resolve_identifier_batch(
            "default_code", {"FORMER-NORMALIZED"}, other_company
        )
        self.assertFalse(scoped["FORMER-NORMALIZED"])
        self.assertEqual(supplierinfo.product_id, canonical.product_variant_id)

        order = self.env["purchase.order"].create({"partner_id": vendor.id})
        wizard = self.env["purchase.order.line.import.wizard"].create({
            "order_id": order.id,
            "file_data": base64.b64encode(
                b"Code,Barcode,Vendor Code,Qty,Price\n"
                b"FORMER-NORMALIZED,,,1,4\n"
                b",1000000000047,,2,4\n"
                b",,FORMER-SUPPLIER,3,4\n"
            ),
            "file_name": "former-identifiers.csv",
        })
        wizard.action_parse()
        mapping_by_column = {
            "Code": "default_code",
            "Barcode": "barcode",
            "Vendor Code": "supplier_code",
            "Qty": "quantity",
            "Price": "price",
        }
        for mapping in wizard.mapping_ids:
            mapping.target = mapping_by_column.get(mapping.source_column)

        product_count = self.env["product.product"].search_count([])
        wizard.action_preview()
        self.assertTrue(wizard.preview_valid)
        self.assertEqual(
            wizard.preview_ids.mapped("product_id"),
            canonical.product_variant_id,
        )
        self.assertEqual(self.env["product.product"].search_count([]), product_count)

        wizard.action_apply()
        self.assertEqual(order.order_line.mapped("product_id"), canonical.product_variant_id)
        self.assertEqual(order.order_line.mapped("product_qty"), [1, 2, 3])
