from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from odoo.addons.pos_order_correction.tests.common import PosOrderCorrectionCommon

from .test_historical_stock import TestHistoricalStock


@tagged("post_install", "-at_install", "historical_consolidation")
class TestConsolidatedHistory(PosOrderCorrectionCommon):
    _movement = TestHistoricalStock._movement
    _target_session = TestHistoricalStock._target_session
    _source = TestHistoricalStock._source
    _prepare = TestHistoricalStock._prepare

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.group_ids = [Command.link(cls.env.ref(name).id) for name in (
            "pos_historical_stock_writeoff.group_historical_stock",
            "product_card_consolidation.group_product_consolidation_manager",
        )]
        cls.company.inventory_valuation = "periodic"
        cls.category = cls.categ_basic.copy({"name": "Consolidation FIFO", "property_cost_method": "fifo"})
        cls.historical_product = cls.create_product("Canonical history", cls.category, 100, 100)
        cls.duplicate = cls.create_product("Duplicate history", cls.category, 100, 200)
        cls.source_location = cls.config.picking_type_id.default_location_src_id
        cls.service = cls.env["product.card.consolidation.service"]

    def _receipts(self):
        first = self._movement(20, "2026-08-28 10:00:00", incoming=True, price=100)
        original = self.historical_product
        self.historical_product = self.duplicate
        second = self._movement(100, "2026-08-28 10:10:00", incoming=True, price=200)
        self.historical_product = original
        return first | second

    def _merge(self, old=False):
        canonical, duplicate = self.historical_product.product_tmpl_id, self.duplicate.product_tmpl_id
        if old:
            self.service.consolidate(canonical, duplicate)
        plan = self.service.analyze(canonical, duplicate, mode="history")
        self.assertFalse(plan["blockers"], plan["blockers"])
        self.service.consolidate(canonical, duplicate, mode="history", expected_fingerprint=plan["fingerprint"])
        return canonical._full_history_operations(self.company)[:1]

    def _consumption(self, quantity=31):
        target = self._target_session()
        source = self._source(quantity)
        picking = self._prepare(source, target)
        picking.historical_effective_at = "2026-08-31 16:00:03"
        return source, picking

    def _zero_sale(self):
        with freeze_time("2026-08-29 10:00:00"):
            self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
            uuid = f"consolidated-zero-sale-{self.session.id}"
            sale = self._create_orders([{
                "pos_order_lines_ui_args": [(self.duplicate, 1)],
                "payments": [(self.cash_pm1, 100)], "customer": self.customer,
                "uuid": uuid,
            }])[uuid]
            self._close_session(self.session)
        # Reproduce an existing zero-valued issue without changing its quantities.
        sale.picking_ids.move_ids.value = 0
        sale.lines.total_cost = 0
        return sale

    def _single_receipt_sale(self, merge=True, old=False):
        original = self.historical_product
        self.historical_product = self.duplicate
        receipt = self._movement(5, "2026-08-28 10:00:00", incoming=True, price=200)
        self.historical_product = original
        sale = self._zero_sale()
        if merge:
            self._merge(old=old)
        return receipt, sale

    def _ordinary_repair(self, sale):
        operation = self.env["pos.cost.recompute"].create({
            "company_id": self.company.id, "selection_type": "orders",
            "order_ids": [Command.set(sale.ids)], "cost_mode": "all",
            "repair_stock_values": True, "reason": "Repair a fully consolidated issue",
        })
        operation.action_preview()
        return operation

    def test_ordinary_repair_after_full_history_conversion(self):
        for old in (False, True):
            with self.subTest(old=old), self.env.cr.savepoint() as savepoint:
                receipt, sale = self._single_receipt_sale(old=old)
                before = receipt.read(["date", "quantity", "value"])
                operation = self._ordinary_repair(sale)
                self.assertEqual(operation.stock_repair_count, 1, operation.stock_line_ids.skip_reason)
                self.assertEqual(operation.stock_line_ids.new_value, 200)
                self.assertTrue(operation.stock_line_ids.snapshot["consolidation"]["complete"])
                self.assertFalse(operation.stock_line_ids.can_recompute_consolidated_history)
                with self.assertRaisesRegex(UserError, "Acknowledge"):
                    operation.action_apply()
                operation.acknowledge_stock_repair = True
                operation.action_apply()
                operation.action_apply()
                self.assertEqual(sale.picking_ids.move_ids.value, 200)
                self.assertEqual(sale.lines.total_cost, 200)
                self.assertEqual(self.historical_product.qty_available, 4)
                self.assertEqual(receipt.read(["date", "quantity", "value"]), before)
                copied = operation.copy()
                self.assertFalse(copied.stock_line_ids)
                self.assertFalse(copied.acknowledge_stock_repair)
                savepoint.rollback()

    def test_incomplete_and_absorbed_history_remain_excluded(self):
        _receipt, sale = self._single_receipt_sale(merge=False)
        self.service.consolidate(self.historical_product.product_tmpl_id, self.duplicate.product_tmpl_id)
        operation = self._ordinary_repair(sale)
        self.assertEqual(operation.stock_repair_count, 0)
        self.assertIn("canonical product", operation.stock_line_ids.skip_reason)
        self.assertIn(self.historical_product.display_name, operation.stock_line_ids.skip_reason)
        self.assertFalse(operation.stock_line_ids.can_recompute_consolidated_history)
        with self.assertRaisesRegex(UserError, "Merge Full History"):
            operation.stock_line_ids.action_recompute_consolidated_history()
        # The target also remains ineligible until every source is converted.
        evidence = operation._stock_consolidation_evidence(self.historical_product)
        self.assertFalse(evidence["complete"])

    def test_multiple_receipts_handoff_and_historical_apply(self):
        self._receipts()
        sale = self._zero_sale()
        self._merge()
        operation = self._ordinary_repair(sale)
        detail = operation.stock_line_ids
        self.assertEqual(operation.stock_repair_count, 0)
        self.assertIn("Multiple earlier receipts", detail.skip_reason)
        self.assertTrue(detail.can_recompute_consolidated_history)
        before = operation.read(["state", "selection_type", "order_ids", "line_ids", "stock_line_ids"])
        action = detail.action_recompute_consolidated_history()
        self.assertEqual(action, detail.action_recompute_consolidated_history())
        self.assertEqual(operation.read(["state", "selection_type", "order_ids", "line_ids", "stock_line_ids"]), before)
        self.assertEqual(sale.lines.total_cost, 0)
        destination = self.env["pos.cost.recompute"].with_context(action["context"]).create({"reason": "Review full FIFO history"})
        self.assertEqual(destination.selection_type, "consolidation")
        self.assertFalse(destination.repair_stock_values or destination.product_ids or destination.config_ids)
        destination.action_preview()
        self.assertEqual(destination.stock_line_ids.new_value, 100)
        destination.action_apply()
        self.assertEqual(sale.lines.total_cost, 100)
        self.assertEqual(sale.picking_ids.move_ids.value, 100)
        self.assertEqual(operation.state, "ready")

    def test_handoff_rights_company_and_current_proof(self):
        self._receipts()
        sale = self._zero_sale()
        self._merge()
        operation = self._ordinary_repair(sale)
        detail = operation.stock_line_ids
        manager = new_test_user(self.env, login="repair-without-history",
            groups="point_of_sale.group_pos_manager,stock.group_stock_manager",
            company_id=self.company.id)
        self.assertFalse(detail.with_user(manager).can_recompute_consolidated_history)
        with self.assertRaises(AccessError):
            detail.with_user(manager).action_recompute_consolidated_history()
        manager.group_ids = [Command.link(self.env.ref("pos_historical_stock_writeoff.group_historical_stock").id)]
        other = self.env["res.company"].create({"name": "Other repair company"})
        manager.company_ids = [Command.link(other.id)]
        action = detail.with_user(manager).with_context(allowed_company_ids=[other.id, self.company.id]).action_recompute_consolidated_history()
        self.assertEqual(action["context"]["default_company_id"], self.company.id)
        with self.assertRaises(AccessError):
            detail.with_user(manager).with_context(allowed_company_ids=[other.id]).action_recompute_consolidated_history()
        rule = self.env["ir.rule"].create({
            "name": "Hide consolidation evidence", "model_id": self.env["ir.model"]._get_id("product.consolidation.operation"),
            "domain_force": "[(\"id\", \"=\", 0)]",
        })
        self.assertFalse(detail.with_user(manager).can_recompute_consolidated_history)
        with self.assertRaises(AccessError):
            detail.with_user(manager).action_recompute_consolidated_history()
        rule.unlink()
        source = self.duplicate
        self.env["stock.move"].create({"product_id": source.id, "product_uom": source.uom_id.id,
            "product_uom_qty": 1, "location_id": self.source_location.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id})
        with self.assertRaisesRegex(UserError, "Merge Full History"):
            detail.action_recompute_consolidated_history()

    def test_absorbed_source_changes_invalidate_ordinary_repair(self):
        _receipt, sale = self._single_receipt_sale()
        operation = self._ordinary_repair(sale)
        operation.acknowledge_stock_repair = True
        for kind in ("move", "quant", "source"):
            with self.subTest(kind=kind), self.env.cr.savepoint() as savepoint:
                if kind == "move":
                    self.env["stock.move"].create({"product_id": self.duplicate.id, "product_uom": self.duplicate.uom_id.id,
                        "product_uom_qty": 1, "location_id": self.source_location.id,
                        "location_dest_id": self.env.ref("stock.stock_location_customers").id})
                elif kind == "quant":
                    self.env["stock.quant"]._update_available_quantity(self.duplicate, self.source_location, 1)
                else:
                    extra = self.create_product("Additional stock-only source", self.category, 100, 200)
                    self.service.consolidate(self.historical_product.product_tmpl_id, extra.product_tmpl_id)
                with self.assertRaisesRegex(UserError, "stale"):
                    operation.action_apply()
                self.assertEqual(sale.picking_ids.move_ids.value, 0)
                self.assertEqual(sale.lines.total_cost, 0)
                savepoint.rollback()

    def test_missing_full_history_proof_is_not_approval(self):
        _receipt, sale = self._single_receipt_sale()
        with patch.object(type(self.historical_product.product_tmpl_id), "_has_full_consolidation_history", None):
            operation = self._ordinary_repair(sale)
        self.assertEqual(operation.stock_repair_count, 0)
        self.assertIn("complete history", operation.stock_line_ids.skip_reason)

    def test_ordinary_repair_does_not_require_history_permission(self):
        _receipt, sale = self._single_receipt_sale()
        manager = new_test_user(self.env, login="ordinary-consolidated-repair",
            groups="point_of_sale.group_pos_manager,stock.group_stock_manager",
            company_id=self.company.id)
        operation = self._ordinary_repair(sale).with_user(manager)
        operation.action_preview()
        self.assertEqual(operation.stock_repair_count, 1)
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.assertEqual(sale.lines.total_cost, 200)

    def test_mixed_repairs_and_single_product_handoff(self):
        _receipt, sale = self._single_receipt_sale()
        # Add an ordinary product and a second fully consolidated product whose
        # multiple receipts require a broader review. Keep all in one selection.
        ordinary = self.create_product("Ordinary mixed repair", self.category, 100, 100)
        canonical = self.historical_product
        self.historical_product = ordinary
        self._movement(5, "2026-08-28 10:00:00", incoming=True)
        self.duplicate = ordinary
        ordinary_sale = self._zero_sale()
        multiple = self.create_product("Multiple mixed repair", self.category, 100, 100)
        self.historical_product = multiple
        self._movement(5, "2026-08-28 10:00:00", incoming=True)
        self._movement(5, "2026-08-28 11:00:00", incoming=True)
        self.duplicate = multiple
        multiple_sale = self._zero_sale()
        self.duplicate = self.create_product("Empty mixed source", self.category, 100, 100)
        self._merge()
        operation = self._ordinary_repair(sale | ordinary_sale | multiple_sale)
        self.assertEqual(operation.stock_repair_count, 2)
        skipped = operation.stock_line_ids.filtered(lambda line: line.status == "skipped")
        self.assertEqual(skipped.product_id, multiple)
        action = skipped.action_recompute_consolidated_history()
        audit = self.env["product.consolidation.operation"].browse(action["context"]["default_consolidation_operation_ids"])
        self.assertEqual(audit.canonical_id, multiple.product_tmpl_id)
        self.assertNotIn(canonical.product_tmpl_id, audit.canonical_id)
        self.assertFalse(action["context"]["default_order_ids"])
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.assertEqual(sale.lines.total_cost, 200)
        self.assertEqual(ordinary_sale.lines.total_cost, 100)
        self.assertEqual(multiple_sale.lines.total_cost, 0)

    def test_old_conversion_then_31_unit_consumption(self):
        self._receipts()
        self._merge(old=True)
        source, picking = self._consumption()
        before = source.read(["state", "date_order", "session_id", "amount_total", "payment_ids"])
        picking.action_apply_historical_stock()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.move_ids.value, 4200)
        self.assertEqual(self.historical_product.qty_available, 89)
        self.assertEqual(source.read(["state", "date_order", "session_id", "amount_total", "payment_ids"]), before)

    def test_unconverted_group_is_explained(self):
        self._receipts()
        self.service.consolidate(self.historical_product.product_tmpl_id, self.duplicate.product_tmpl_id)
        _source, picking = self._consumption(10)
        with self.assertRaisesRegex(UserError, "Merge Full History"):
            picking.action_apply_historical_stock()

    def test_manual_recompute_includes_pos_before_consumption(self):
        receipts = self._receipts()
        with freeze_time("2026-08-29 10:00:00"):
            self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
            sale = self._create_orders([{
                "pos_order_lines_ui_args": [(self.duplicate, 4)],
                "payments": [(self.cash_pm1, 400)], "customer": self.customer,
                "uuid": "before-history-merge",
            }])["before-history-merge"]
            self._close_session(self.session)
        self.assertEqual(sale.lines.total_cost, 800)
        before = sale.read(["state", "date_order", "session_id", "amount_total", "payment_ids"])
        receipt_values = receipts.mapped("value")
        audit = self._merge()
        self.assertEqual(sale.lines.product_id, self.historical_product)
        self.assertEqual(sale.lines.total_cost, 800)
        source, picking = self._consumption()
        picking.action_apply_historical_stock()
        operation = self.env["pos.cost.recompute"].browse(source.action_prepare_cost_recompute()["res_id"])
        operation.reason = "Recompute unified history from its earliest affected issue"
        operation.action_preview()
        self.assertLess(operation.history_start_at, picking.historical_effective_at)
        self.assertEqual(operation.history_start_at, audit.earliest_issue_at)
        self.assertEqual(operation.line_ids.new_cost, 400)
        operation.action_apply()
        self.assertEqual(sale.lines.total_cost, 400)
        self.assertEqual(sale.picking_ids.move_ids.value, 400)
        self.assertEqual(receipts.mapped("value"), receipt_values)
        self.assertEqual(sale.read(["state", "date_order", "session_id", "amount_total", "payment_ids"]), before)

    def test_manual_stock_only_consolidation_plan(self):
        self._receipts()
        original = self.historical_product
        self.historical_product = self.duplicate
        issue = self._movement(4, "2026-08-29 10:00:00")
        self.historical_product = original
        self.assertEqual(issue.value, 800)
        audit = self._merge(old=True)
        action = audit.action_recompute_costs()
        operation = self.env["pos.cost.recompute"].with_context(action["context"]).create({"reason": "Manual stock-only recomputation"})
        operation.action_preview()
        self.assertFalse(operation.line_ids)
        self.assertEqual(operation.stock_line_ids.new_value, 400)
        self.assertTrue(operation.can_apply)
        operation.action_apply()
        self.assertEqual(issue.value, 400)
        self.assertEqual(self.historical_product.qty_available, 116)

    def test_merged_history_still_rejects_shortage(self):
        self._receipts()
        self._merge()
        _source, picking = self._consumption(121)
        with self.assertRaises(UserError):
            picking.action_apply_historical_stock()
        self.assertEqual(picking.state, "draft")

    def test_previously_applied_writeoff_and_cost_audit_survive(self):
        self._receipts()
        original = self.historical_product
        self.historical_product = self.duplicate
        source, picking = self._consumption(4)
        picking.action_apply_historical_stock()
        action = source.action_prepare_cost_recompute()
        recompute = self.env["pos.cost.recompute"].browse(action["res_id"])
        recompute.reason = "Record original source valuation"
        recompute.action_preview()
        recompute.action_apply()
        self._close_session(self.config.current_session_id)
        evidence = recompute.stock_line_ids.read(["product_id", "old_value", "new_value"])
        before = picking.move_ids.read(["date", "quantity", "value", "state", "historical_cost_line_id"])
        self.historical_product = original
        operation = self._merge()
        self.assertEqual(picking.move_ids.product_id, original)
        self.assertEqual(source.lines.product_id, original)
        self.assertEqual(picking.move_ids.read(["date", "quantity", "value", "state", "historical_cost_line_id"]), before)
        self.assertEqual(recompute.stock_line_ids.read(["product_id", "old_value", "new_value"]), evidence)
        self.assertTrue(operation.line_ids.filtered(lambda line: line.record_model == "stock.move" and line.record_id == picking.move_ids.id))

    def test_standard_valuation_report_excludes_retired_pairs(self):
        report = self.env["stock_account.stock.valuation.report"]
        before = report._get_report_data()["ending_stock"]["value"]
        self._receipts()
        original = self.historical_product
        self.historical_product = self.duplicate
        self._movement(4, "2026-08-29 10:00:00")
        self.historical_product = original
        self._merge(old=True)
        self.assertEqual(self.historical_product.total_value, 21600)
        after = report._get_report_data()["ending_stock"]["value"]
        self.assertAlmostEqual(after - before, 21600, places=2)

    def test_empty_and_stale_consolidated_cost_plans(self):
        receipts = self._receipts()
        audit = self._merge()
        action = audit.action_recompute_costs()
        operation = self.env["pos.cost.recompute"].with_context(action["context"]).create({"reason": "Review merged costs"})
        operation.action_preview()
        self.assertFalse(operation.stock_line_ids)
        self.assertFalse(operation.can_apply)
        issue = self._movement(4, "2026-08-29 10:00:00")
        operation.action_preview()
        before = issue.value
        receipts[:1].value += 1
        with self.assertRaises(UserError), self.env.cr.savepoint():
            operation.action_apply()
        self.assertEqual(issue.value, before)

    def test_new_source_merge_invalidates_prepared_cost_plan(self):
        self._receipts()
        self._movement(4, "2026-08-29 10:00:00")
        audit = self._merge()
        action = audit.action_recompute_costs()
        operation = self.env["pos.cost.recompute"].with_context(action["context"]).create({"reason": "Plan before another merge"})
        operation.action_preview()
        self.duplicate = self.create_product("Next source", self.category, 100, 200)
        self._merge()
        with self.assertRaises(UserError), self.env.cr.savepoint():
            operation.action_apply()
