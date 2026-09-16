from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tests.common import new_test_user

from .test_product_card_consolidation import TestProductCardConsolidation


@tagged("post_install", "-at_install", "product_full_history")
class TestFullHistoryConsolidation(TransactionCase):
    _stock_products = TestProductCardConsolidation._stock_products
    _make_stock_move = TestProductCardConsolidation._make_stock_move
    _receive = TestProductCardConsolidation._receive
    _deliver = TestProductCardConsolidation._deliver

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [Command.link(cls.env.ref("product_card_consolidation.group_product_consolidation_manager").id)]
        cls.ProductTemplate = cls.env["product.template"]
        cls.Service = cls.env["product.card.consolidation.service"]
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.fifo_category = cls.env["product.category"].create({
            "name": "Full history FIFO", "property_cost_method": "fifo", "property_valuation": "periodic",
        })
        cls.start = fields.Datetime.now() - timedelta(days=30)

    def _merge(self, canonical, duplicate):
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        self.assertFalse(plan["blockers"], plan["blockers"])
        self.Service.consolidate(canonical, duplicate, mode="history", expected_fingerprint=plan["fingerprint"])
        return canonical._full_history_operations(self.env.company)[:1]

    def _history(self, old=False):
        canonical, duplicate = self._stock_products()
        a, b = canonical.product_variant_id, duplicate.product_variant_id
        r1 = self._receive(a, 20, 8, date=self.start)
        r2 = self._receive(b, 100, 9, date=self.start + timedelta(minutes=10))
        s1 = self._deliver(b, 4, date=self.start + timedelta(days=2))
        s2 = self._deliver(a, 19, date=self.start + timedelta(days=3))
        if old:
            self.Service.consolidate(canonical, duplicate)
        return canonical, duplicate, r1 | r2 | s1 | s2

    def test_merge_original_receipts_and_current_stock(self):
        canonical, duplicate, real = self._history()
        original = [(m.id, m.date, m.quantity, m.value, m.state) for m in real]
        operation = self._merge(canonical, duplicate)
        self.assertEqual([(m.id, m.date, m.quantity, m.value, m.state) for m in real], original)
        self.assertEqual(real.product_id, canonical.product_variant_id)
        self.assertEqual(canonical.product_variant_id.qty_available, 97)
        self.assertEqual(canonical.product_variant_id.with_context(to_date=self.start + timedelta(days=1)).qty_available, 120)
        self.assertFalse(duplicate.active)
        self.assertTrue(canonical._has_full_consolidation_history(self.env.company))
        self.assertTrue(operation.line_ids)
        self.assertEqual(operation.earliest_issue_at, self.start + timedelta(days=2))

    def test_convert_old_pair_and_retry(self):
        canonical, duplicate, real = self._history(old=True)
        pair_in = self.env["stock.move"].search([("consolidation_source_receipt_id", "in", real.ids)])
        pair = pair_in | pair_in.consolidation_out_move_id
        original = [(m.date, m.quantity, m.value) for m in pair]
        self.assertEqual(pair_in.quantity, 96)
        operation = self._merge(canonical, duplicate)
        self.assertEqual([(m.date, m.quantity, m.value) for m in pair], original)
        self.assertEqual(set(pair.mapped("state")), {"cancel"})
        self.assertFalse(any(m.is_in or m.is_out for m in pair))
        self.assertEqual(pair.consolidation_retired_operation_id, operation)
        a = canonical.product_variant_id
        self.assertEqual(a.qty_available, 97)
        self.assertEqual(a._run_fifo(97), 873)
        self.assertFalse(set(pair.ids) & {move.id for move in a._run_fifo_get_stack()[0]})
        self.Service.consolidate(canonical, duplicate, mode="history", expected_fingerprint=operation.fingerprint)
        self.assertEqual(len(canonical._full_history_operations(self.env.company)), 1)
        with self.assertRaises(AccessError):
            pair.write({"state": "done"})

    def test_archived_source_without_previous_merge(self):
        canonical, duplicate, real = self._history()
        duplicate.action_archive()
        self._merge(canonical, duplicate)
        self.assertEqual(real.product_id, canonical.product_variant_id)

    def test_archived_card_action_preserves_explicit_pair(self):
        canonical, duplicate, _real = self._history(old=True)
        action = duplicate.action_open_history_consolidation()
        wizard = self.env["product.consolidation.wizard"].with_context(
            active_model="product.template", active_ids=duplicate.ids, **action["context"],
        ).create({})
        self.assertEqual(wizard.mode, "history")
        self.assertEqual(wizard.canonical_template_id, canonical)
        self.assertEqual(set(wizard.product_template_ids.ids), set((canonical | duplicate).ids))
        wizard.action_request_confirmation()
        wizard.action_confirm()
        self.assertTrue(canonical._has_full_consolidation_history(self.env.company))

    def test_preserve_purchase_values(self):
        canonical, duplicate = self._stock_products()
        partner = self.env["res.partner"].create({"name": "History vendor"})
        order = self.env["purchase.order"].create({"partner_id": partner.id})
        line = self.env["purchase.order.line"].create({
            "order_id": order.id, "product_id": duplicate.product_variant_id.id,
            "product_qty": 100, "product_uom_id": duplicate.uom_id.id, "price_unit": 9,
            "name": "Original entered description", "discount": 3,
        })
        receipt = self._receive(duplicate.product_variant_id, 100, 9, date=self.start, purchase_line=line)
        before = (line.name, line.product_qty, line.price_unit, line.discount, line.price_subtotal,
                  line.tax_ids.ids, line.qty_received, order.amount_total)
        self._merge(canonical, duplicate)
        self.assertEqual(line.product_id, canonical.product_variant_id)
        self.assertEqual(receipt.purchase_line_id, line)
        self.assertEqual((line.name, line.product_qty, line.price_unit, line.discount, line.price_subtotal,
                          line.tax_ids.ids, line.qty_received, order.amount_total), before)

    def test_reject_unfinished_and_reserved_history(self):
        canonical, duplicate, _real = self._history()
        self.env["stock.move"].create({"product_id": duplicate.product_variant_id.id,
            "product_uom": duplicate.uom_id.id, "product_uom_qty": 1,
            "location_id": self.stock_location.id, "location_dest_id": self.customer_location.id})
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        self.assertIn("open_moves", [line["category"] for line in plan["blockers"]])

    def test_stale_preview_and_rollback(self):
        canonical, duplicate, real = self._history()
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        real[:1].date += timedelta(minutes=1)
        with self.assertRaises(UserError):
            self.Service.consolidate(canonical, duplicate, mode="history", expected_fingerprint=plan["fingerprint"])
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        before = real.product_id
        with patch.object(type(self.Service), "_history_after_rewrite", side_effect=UserError("Late failure")):
            with self.assertRaises(UserError):
                self.Service.consolidate(canonical, duplicate, mode="history", expected_fingerprint=plan["fingerprint"])
        self.assertEqual(real.product_id, before)
        self.assertTrue(duplicate.active)
        self.assertFalse(canonical._full_history_operations(self.env.company))
        self._merge(canonical, duplicate)

    def test_audit_cannot_be_forged_or_changed(self):
        canonical, duplicate, _real = self._history()
        with self.assertRaises(AccessError):
            self.env["product.consolidation.operation"].with_context(product_history_consolidation_internal=True).create({})
        operation = self._merge(canonical, duplicate)
        for action in (lambda: operation.write({"reason": "Changed"}), operation.unlink, operation.copy):
            with self.assertRaises(AccessError):
                action()

    def test_mode_change_invalidates_confirmation(self):
        canonical, duplicate, _real = self._history()
        wizard = self.env["product.consolidation.wizard"].create({
            "product_template_ids": [Command.set((canonical | duplicate).ids)],
            "canonical_template_id": canonical.id,
        })
        wizard.action_request_confirmation()
        wizard.mode = "history"
        self.assertEqual(wizard.state, "preview")
        self.assertFalse(wizard.analysis_fingerprint)
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_old_mode_after_history_requires_new_conversion(self):
        canonical, duplicate, _real = self._history()
        self._merge(canonical, duplicate)
        next_source = self.ProductTemplate.create({"name": "Next source", "type": "consu",
            "is_storable": True, "company_id": self.env.company.id, "categ_id": self.fifo_category.id})
        receipt = self._receive(next_source.product_variant_id, 5, 10, date=self.start)
        self.Service.consolidate(canonical, next_source)
        self.assertEqual(receipt.product_id.product_tmpl_id, next_source)
        self.assertFalse(canonical._has_full_consolidation_history(self.env.company))
        self._merge(canonical, next_source)
        self.assertTrue(canonical._has_full_consolidation_history(self.env.company))

    def test_multiple_old_sources_are_converted_together(self):
        canonical, duplicate, _real = self._history(old=True)
        other = self.ProductTemplate.create({"name": "Other old source", "type": "consu",
            "is_storable": True, "company_id": self.env.company.id, "categ_id": self.fifo_category.id})
        receipt = self._receive(other.product_variant_id, 5, 10, date=self.start)
        self.Service.consolidate(canonical, other)
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        self.assertEqual(set(plan["sources"].ids), {duplicate.id, other.id})
        operation = self._merge(canonical, duplicate)
        self.assertEqual(set(operation.source_ids.ids), {duplicate.id, other.id})
        self.assertEqual(receipt.product_id, canonical.product_variant_id)
        self.assertEqual(canonical.product_variant_id.qty_available, 102)

    def test_inconsistent_old_pair_blocks_the_entire_group(self):
        canonical, duplicate, real = self._history(old=True)
        pair_in = self.env["stock.move"].search([("consolidation_source_receipt_id", "in", real.ids)])
        pair_in.value += 1
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        self.assertIn("old_pair", [line["category"] for line in plan["blockers"]])
        with self.assertRaises(UserError):
            self.Service.consolidate(canonical, duplicate, mode="history", expected_fingerprint=plan["fingerprint"])
        self.assertEqual(pair_in.state, "done")

    def test_unauthorized_history_api_and_foreign_company(self):
        canonical, duplicate, real = self._history()
        user = new_test_user(self.env, login="history_merge_no_privilege", groups="base.group_user")
        with self.assertRaises(AccessError):
            self.Service.with_user(user).analyze(canonical, duplicate, mode="history")
        company = self.env["res.company"].create({"name": "Other history company"})
        other = duplicate.copy({"name": "Other company source", "company_id": company.id})
        with self.assertRaises(AccessError):
            self.Service.with_context(allowed_company_ids=self.env.company.ids).analyze(canonical, other, mode="history")

    def test_financial_reference_and_period_lock_block_preview(self):
        canonical, duplicate, _real = self._history()
        account = self.env["account.account"].search([("company_ids", "in", self.env.company.ids)], limit=1)
        journal = self.env["account.journal"].search([("company_id", "=", self.env.company.id)], limit=1)
        entry = self.env["account.move"].create({"journal_id": journal.id})
        self.env["account.move.line"].with_context(check_move_validity=False).create({
            "move_id": entry.id, "account_id": account.id, "name": "Protected product reference",
            "product_id": duplicate.product_variant_id.id, "debit": 0, "credit": 0,
        })
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        self.assertIn("financial", [line["category"] for line in plan["blockers"]])
        entry.unlink()
        self.env.company.fiscalyear_lock_date = self.start.date()
        plan = self.Service.analyze(canonical, duplicate, mode="history")
        self.assertIn("period", [line["category"] for line in plan["blockers"]])

    def test_preserve_sale_line_values_and_source_links(self):
        canonical, duplicate = self._stock_products()
        partner = self.env["res.partner"].create({"name": "History customer"})
        order = self.env["sale.order"].create({"partner_id": partner.id})
        line = self.env["sale.order.line"].create({"order_id": order.id,
            "product_id": duplicate.product_variant_id.id, "product_uom_qty": 3,
            "price_unit": 17, "discount": 5, "name": "Entered sale description"})
        before = line.read(["name", "price_unit", "discount", "product_uom_qty", "tax_ids", "price_total"])
        self._merge(canonical, duplicate)
        self.assertEqual(line.product_id, canonical.product_variant_id)
        self.assertEqual(line.product_template_id, canonical)
        self.assertEqual(line.read(["name", "price_unit", "discount", "product_uom_qty", "tax_ids", "price_total"]), before)

    def test_nonstock_cards_and_cancellation_remain_supported(self):
        canonical, duplicate = self.ProductTemplate.create([
            {"name": name, "type": "service", "company_id": self.env.company.id} for name in ("Service A", "Service B")
        ])
        wizard = self.env["product.consolidation.wizard"].create({"mode": "history",
            "product_template_ids": [Command.set((canonical | duplicate).ids)], "canonical_template_id": canonical.id})
        wizard.action_request_confirmation()
        wizard.action_back_to_preview()
        self.assertTrue(duplicate.active)
        self.assertFalse(canonical._full_history_operations(self.env.company))
        self._merge(canonical, duplicate)
        self.assertFalse(duplicate.active)

    def test_packaged_history_preserves_dimensions(self):
        canonical, duplicate = self._stock_products()
        package = self.env["stock.package"].create({"name": "History package"})
        receipt = self._receive(duplicate.product_variant_id, 10, 9, date=self.start, package=package)
        self._merge(canonical, duplicate)
        self.assertEqual(receipt.move_line_ids.result_package_id, package)
        quants = self.env["stock.quant"].search([("package_id", "=", package.id)])
        self.assertEqual(quants.product_id, canonical.product_variant_id)
        self.assertEqual(sum(quants.mapped("quantity")), 10)

    def test_return_keeps_original_link(self):
        canonical, duplicate = self._stock_products()
        self._receive(duplicate.product_variant_id, 10, 9, date=self.start)
        issue = self._deliver(duplicate.product_variant_id, 4, date=self.start + timedelta(days=1))
        returned = self._make_stock_move(duplicate.product_variant_id, 2, self.customer_location,
                                        self.stock_location, date=self.start + timedelta(days=2))
        returned.origin_returned_move_id = issue
        before = returned.value
        self._merge(canonical, duplicate)
        self.assertEqual(returned.origin_returned_move_id, issue)
        self.assertEqual(returned.product_id, canonical.product_variant_id)
        self.assertEqual(returned.value, before)
        self.assertEqual(canonical.product_variant_id.qty_available, 8)

    def test_zero_stock_source_and_unknown_reference_blocker(self):
        canonical, duplicate = self._stock_products()
        receipt = self._receive(duplicate.product_variant_id, 4, 9, date=self.start)
        issue = self._deliver(duplicate.product_variant_id, 4, date=self.start + timedelta(days=1))
        self.assertEqual(duplicate.product_variant_id.qty_available, 0)
        self._merge(canonical, duplicate)
        self.assertEqual((receipt | issue).product_id, canonical.product_variant_id)
        other = canonical.copy({"name": "Unsupported scrap source"})
        scrap = self.env["stock.scrap"].create({"product_id": other.product_variant_id.id})
        plan = self.Service.analyze(canonical, other, mode="history")
        self.assertTrue(any("stock.scrap" in line["message"] for line in plan["blockers"]))
        with self.assertRaises(UserError):
            self.Service.consolidate(canonical, other, mode="history", expected_fingerprint=plan["fingerprint"])
        self.assertTrue(other.active)
        self.assertEqual(scrap.product_id.product_tmpl_id, other)
