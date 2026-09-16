from freezegun import freeze_time

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

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
