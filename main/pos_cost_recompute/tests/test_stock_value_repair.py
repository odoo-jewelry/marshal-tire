import json
import logging
from datetime import timedelta
from time import perf_counter
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon

from .test_pos_cost_recompute import TestPosCostRecompute


@tagged("post_install", "-at_install")
class TestStockValueRepair(TestPoSCommon):
    _orders = TestPosCostRecompute._orders
    _operation = TestPosCostRecompute._operation

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.Operation = self.env["pos.cost.recompute"]
        self.category = self.categ_basic.copy({
            "name": "Historical zero stock", "property_cost_method": "standard",
            "property_valuation": "periodic",
        })
        self.day = fields.Datetime.now() - timedelta(days=10)

    def _receipt(self, product, quantity=1, value=284.01, day=0):
        warehouse = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        move = self.env["stock.move"].create({
            "product_id": product.id, "product_uom": product.uom_id.id,
            "product_uom_qty": quantity, "value_manual": value,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": warehouse.lot_stock_id.id,
            "picking_type_id": warehouse.in_type_id.id,
        })
        move._action_confirm()
        move.quantity = quantity
        move.picked = True
        move._action_done()
        move.date = self.day + timedelta(days=day)
        return move

    def _fixture(self, prices=(284.01,), quantities=None, sale_quantities=None, invoiced=False):
        quantities = quantities or [1] * len(prices)
        sale_quantities = sale_quantities or [1] * len(prices)
        products = self.env["product.product"]
        receipts = self.env["stock.move"]
        for index, price in enumerate(prices):
            product = self.create_product(f"Zero stock {index}", self.category, 1000, 0)
            products |= product
            receipts |= self._receipt(product, quantities[index], price * quantities[index])
        orders = self._orders(list(zip(products, sale_quantities)), invoiced=invoiced)
        issues = orders.picking_ids.move_ids
        issues.date = self.day + timedelta(days=2)
        self.assertFalse(any(issues.mapped("value")))
        self.category.property_cost_method = "fifo"
        return products, receipts, orders, issues

    def _earlier_issue(self, source, quantity, day=1, destination=None):
        move = self.env["stock.move"].create({
            "product_id": source.product_id.id, "product_uom": source.product_uom.id,
            "product_uom_qty": quantity, "location_id": source.location_id.id,
            "location_dest_id": (destination or source.location_dest_id).id,
        })
        move._action_confirm()
        move.quantity = quantity
        move.picked = True
        move._action_done()
        move.date = self.day + timedelta(days=day)
        return move

    def _repair(self, orders, apply=False):
        operation = self._operation(orders, repair_stock_values=True)
        if apply:
            operation.acknowledge_stock_repair = True
            operation.action_apply()
        return operation

    def test_preview_totals_apply_and_later_receipt(self):
        products, receipts, orders, issues = self._fixture((284.01, 491.75, 38.70), [1, 1, 4])
        self._receipt(products[0], value=900, day=4)
        before = products.read(["standard_price", "qty_available", "total_value"])
        dimensions = issues.read(["quantity", "date", "location_id", "location_dest_id"])
        operation = self._repair(orders)
        self.assertEqual(operation.stock_repair_count, 3, operation.stock_line_ids.mapped("skip_reason"))
        self.assertAlmostEqual(sum(operation.stock_line_ids.mapped("new_value")), 814.46)
        self.assertAlmostEqual(sum(operation.line_ids.mapped("new_cost")), 814.46)
        self.assertFalse(any(issues.mapped("value")))
        self.assertFalse(issues.cost_repair_line_id)
        self.assertEqual(products.read(["standard_price", "qty_available", "total_value"]), before)
        with self.assertRaisesRegex(UserError, "Acknowledge"), self.env.cr.savepoint():
            operation.action_apply()
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.assertEqual(operation.state, "done")
        self.assertAlmostEqual(sum(issues.mapped("value")), 814.46)
        self.assertAlmostEqual(sum(orders.lines.mapped("total_cost")), 814.46)
        self.assertAlmostEqual(sum(orders.mapped("margin")), 2185.54)
        self.env.flush_all()
        report = self.env["report.pos.order"].search([("order_id", "in", orders.ids)])
        self.assertAlmostEqual(sum(report.mapped("margin")), 2185.54)
        self.assertEqual(issues.read(["quantity", "date", "location_id", "location_dest_id"]), dimensions)
        self.assertEqual(products.read(["standard_price", "qty_available", "total_value"]), before)
        self.assertEqual(issues.cost_repair_line_id, operation.stock_line_ids)
        issues._set_value()
        self.assertAlmostEqual(sum(issues.mapped("value")), 814.46)
        operation.action_apply()
        ordinary = self._operation(orders)
        self.assertEqual(ordinary.unchanged_count, 3)
        receipts[0].value_manual = 400
        self.assertAlmostEqual(issues[0].value, 284.01)
        self.assertAlmostEqual(orders[0].lines.total_cost, 284.01)

    def test_protected_value_history_copy_and_removal(self):
        _products, _receipts, orders, issues = self._fixture()
        operation = self._repair(orders, apply=True)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            issues.value_manual = 9
        with self.assertRaises(UserError), self.env.cr.savepoint():
            self.env["product.value"].create({"move_id": issues.id, "value": 9})
        self.assertFalse(self.env["product.value"].search([("move_id", "=", issues.id)]))
        for vals in ({"value": 9}, {"quantity": 2}, {"date": fields.Datetime.now()}):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                issues.write(vals)
        with self.assertRaises(UserError), self.env.cr.savepoint():
            issues.move_line_ids.quantity = 2
        with self.assertRaises(UserError), self.env.cr.savepoint():
            issues.move_line_ids.quantity_product_uom = 2
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            issues.with_context(pos_cost_recompute_internal=True).cost_repair_line_id = False
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            operation.stock_line_ids.write({"new_value": 9})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            operation.stock_line_ids.unlink()
        copied = operation.copy()
        self.assertTrue(copied.repair_stock_values)
        self.assertFalse(copied.acknowledge_stock_repair)
        self.assertFalse(copied.stock_line_ids | copied.line_ids.stock_line_ids)
        module = self.env.ref("base.module_pos_cost_recompute")
        for method in (module.button_uninstall, module.module_uninstall):
            with self.assertRaisesRegex(UserError, "cannot be removed"), self.env.cr.savepoint():
                method()
        with self.assertRaisesRegex(UserError, "cannot be removed"), self.env.cr.savepoint():
            module.write({"state": "to remove"})
        self.assertEqual(module.state, "installed")

    def test_rollback_after_stock_write(self):
        _products, _receipts, orders, issues = self._fixture()
        operation = self._repair(orders)
        operation.acknowledge_stock_repair = True
        def fail(lines, moves):
            self.assertAlmostEqual(issues.value, 284.01)
            raise UserError("Simulated POS failure after stock write")
        with patch.object(type(orders.lines), "_compute_total_cost", fail):
            with self.assertRaisesRegex(UserError, "Simulated POS failure"):
                operation.action_apply()
        self.assertEqual(issues.value, 0)
        self.assertFalse(issues.cost_repair_line_id)
        self.assertEqual(orders.lines.total_cost, 0)
        self.assertEqual(operation.state, "ready")
        self.assertEqual(operation.stock_line_ids.actual_value, 0)

    def test_stale_receipt_return_quantity_and_settings(self):
        products, receipts, orders, issues = self._fixture()
        operation = self._repair(orders)
        operation.acknowledge_stock_repair = True
        for record, vals in ((receipts, {"value": 400}), (products, {"tracking": "lot"}),
                             (orders.lines, {"total_cost": 12})):
            with self.env.cr.savepoint() as savepoint:
                record.write(vals)
                with self.assertRaisesRegex(UserError, "stale"):
                    operation.action_apply()
                savepoint.rollback()
        returned = self.env["stock.move"].create({
            "product_id": products.id, "product_uom": products.uom_id.id,
            "product_uom_qty": 1, "origin_returned_move_id": issues.id,
            "location_id": issues.location_dest_id.id, "location_dest_id": issues.location_id.id,
        })
        with self.assertRaisesRegex(UserError, "stale"):
            operation.action_apply()
        self.assertEqual(returned.state, "draft")
        self.assertEqual(issues.value, 0)

    def test_permissions_default_cancel_and_reset(self):
        _products, _receipts, orders, issues = self._fixture()
        pos_only = new_test_user(self.env, login="repair-pos-only", groups="point_of_sale.group_pos_manager")
        stock_only = new_test_user(self.env, login="repair-stock-only", groups="stock.group_stock_manager")
        ordinary = self._operation(orders, preview=False)
        self.assertFalse(ordinary.repair_stock_values)
        ordinary.with_user(pos_only).action_preview()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            ordinary.with_user(pos_only).repair_stock_values = True
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            ordinary.with_user(stock_only).action_preview()
        operation = self._repair(orders)
        operation.acknowledge_stock_repair = True
        operation.cost_mode = "zero"
        self.assertFalse(operation.acknowledge_stock_repair)
        self.assertFalse(operation.stock_line_ids)
        operation.action_preview()
        operation.action_cancel()
        self.assertEqual(issues.value, 0)
        with self.assertRaises(UserError):
            operation.action_apply()

    def test_exclusions(self):
        products, receipts, orders, issues = self._fixture()
        cases = [
            (self.category, {"property_cost_method": "average"}, "FIFO"),
            (self.category, {"property_valuation": "real_time"}, "periodic"),
            (products, {"tracking": "lot"}, "untracked"),
            (receipts, {"value": 0}, "positive finite"),
            (receipts, {"date": issues.date}, "Equal movement timestamps"),
            (receipts.location_id, {"usage": "customer"}, "supplier"),
            (self.env.company, {"fiscalyear_lock_date": fields.Date.today()}, "locked period"),
        ]
        for record, vals, reason in cases:
            with self.subTest(vals=vals), self.env.cr.savepoint() as savepoint:
                record.write(vals)
                operation = self._repair(orders)
                self.assertEqual(operation.stock_repair_count, 0)
                self.assertIn(reason, operation.stock_line_ids.skip_reason)
                savepoint.rollback()

    def test_multiple_receipts_and_consumption(self):
        products, _receipts, orders, _issues = self._fixture()
        self._receipt(products, value=200, day=1)
        operation = self._repair(orders)
        self.assertIn("Exactly one", operation.stock_line_ids.skip_reason)

    def test_future_standard_return(self):
        products, _receipts, orders, issues = self._fixture()
        self._repair(orders, apply=True)
        self._receipt(products, value=900, day=4)
        line = self.env["pos.order.line"].new({
            "product_id": products.id, "qty": -1, "refunded_orderline_id": orders.lines.id,
        })
        pickings = self.env["stock.picking"]._create_picking_from_pos_order_lines(
            issues.location_dest_id.id, line, self.config.picking_type_id, self.customer,
        )
        self.assertEqual(pickings.state, "done")
        self.assertEqual(pickings.move_ids.origin_returned_move_id, issues)
        self.assertAlmostEqual(pickings.move_ids.value, 284.01)

    def test_prior_consumption_negative_history_and_internal_transfer(self):
        _products, _receipts, orders, issues = self._fixture(quantities=[4], sale_quantities=[2])
        with self.env.cr.savepoint() as savepoint:
            self._earlier_issue(issues, 3)
            operation = self._repair(orders)
            self.assertIn("insufficient", operation.stock_line_ids.skip_reason)
            savepoint.rollback()
        with self.env.cr.savepoint() as savepoint:
            self._earlier_issue(issues, 1, day=-1)
            operation = self._repair(orders)
            self.assertIn("negative stock", operation.stock_line_ids.skip_reason)
            savepoint.rollback()
        destination = self.env["stock.location"].create({
            "name": "Ambiguous internal location", "usage": "internal", "company_id": self.env.company.id,
        })
        self._earlier_issue(issues, 1, destination=destination)
        self.assertEqual(self._repair(orders).stock_repair_count, 0)

    def test_shared_move_full_selection_and_partial_selection(self):
        _products, _receipts, orders, issues = self._fixture(quantities=[2], sale_quantities=[2])
        orders.lines.write({"qty": 1, "price_subtotal": 1000, "price_subtotal_incl": 1000})
        second = orders.lines.copy({"qty": 1, "total_cost": 77})
        partial = self._operation(orders, repair_stock_values=True, cost_mode="zero")
        self.assertEqual(partial.stock_repair_count, 0)
        self.assertIn("All POS lines", partial.stock_line_ids.skip_reason)
        operation = self._repair(orders, apply=True)
        self.assertEqual(operation.stock_repair_count, 1)
        self.assertEqual(len(operation.line_ids), 2)
        self.assertAlmostEqual(issues.value, 568.02)
        self.assertAlmostEqual(second.total_cost, 284.01)
        self.assertEqual(operation.stock_line_ids.pos_line_ids, orders.lines)

    def test_mixed_normal_repair_and_exclusion(self):
        _products, receipts, orders, issues = self._fixture((284.01, 50, 100))
        issues[1].value = 22
        receipts[2].value = 0
        operation = self._repair(orders, apply=True)
        self.assertEqual(operation.stock_repair_count, 1)
        self.assertEqual(operation.changed_count, 2)
        self.assertEqual(operation.skipped_count, 1)
        self.assertEqual(issues.mapped("value"), [284.01, 22, 0])
        self.assertEqual(orders.lines.mapped("total_cost"), [284.01, 22, 0])

    def test_nonfinite_source_consignment_and_consolidation(self):
        products, receipts, orders, _issues = self._fixture()
        with self.env.cr.savepoint() as savepoint:
            # ORM monetary writes reject NaN. Simulate corrupt source input in
            # the cache to exercise the analyser without bypassing DB writes.
            receipts._fields["value"]._update_cache(receipts, float("nan"))
            operation = self._repair(orders)
            self.assertEqual(operation.stock_repair_count, 0)
            self.assertIn("positive finite", operation.stock_line_ids.skip_reason)
            savepoint.rollback()
        with self.env.cr.savepoint() as savepoint:
            receipts.move_line_ids.owner_id = self.customer
            self.assertEqual(self._repair(orders).stock_repair_count, 0)
            savepoint.rollback()
        if "merged_into_id" in products._fields:
            duplicate = products.product_tmpl_id.copy()
            duplicate.with_context(product_consolidation_write=True).merged_into_id = products.product_tmpl_id
            self.assertIn("Consolidated", self._repair(orders).stock_line_ids.skip_reason)

    def test_financial_and_analytic_exclusions(self):
        _products, _receipts, orders, issues = self._fixture()
        journal = self.env["account.journal"].search([
            ("company_id", "=", self.env.company.id), ("type", "=", "general"),
        ], limit=1)
        entry = self.env["account.move"].create({"journal_id": journal.id})
        for record, vals in ((issues, {"account_move_id": entry.id}), (orders, {"account_move": entry.id})):
            with self.env.cr.savepoint() as savepoint:
                record.write(vals)
                self.assertIn("accounting", self._repair(orders).stock_line_ids.skip_reason)
                savepoint.rollback()
        plan = self.env["account.analytic.plan"].create({"name": "Stock repair exclusion"})
        account = self.env["account.analytic.account"].create({"name": "Existing costs", "plan_id": plan.id})
        analytic = self.env["account.analytic.line"].create({
            "name": "Existing stock analytic cost", "account_id": account.id, "amount": -10,
        })
        issues.analytic_account_line_ids = [Command.link(analytic.id)]
        self.assertIn("analytic", self._repair(orders).stock_line_ids.skip_reason)

    def test_invoiced_order_is_excluded_and_normal_mode_preserves_it(self):
        _products, _receipts, orders, issues = self._fixture(invoiced=True)
        self.assertTrue(orders.account_move)
        values = orders.account_move.line_ids.read(["debit", "credit", "balance"])
        self.assertEqual(self._repair(orders).stock_repair_count, 0)
        ordinary = self._operation(orders)
        ordinary.allow_zero_cost = True
        ordinary.action_apply()
        self.assertEqual(orders.account_move.line_ids.read(["debit", "credit", "balance"]), values)
        self.assertEqual(issues.value, 0)

    def test_foreign_currency_uses_order_date(self):
        self.config = self.other_currency_config
        self.bank_pm1, self.cash_pm1 = self.bank_pm2, self.cash_pm2
        products, _receipts, orders, issues = self._fixture()
        day = fields.Date.today() - timedelta(days=10)
        rate = self.env["res.currency.rate"].create({
            "currency_id": self.other_currency.id, "company_id": self.env.company.id,
            "name": day, "rate": 0.25,
        })
        orders.date_order = fields.Datetime.to_datetime(day)
        operation = self._repair(orders)
        self.assertAlmostEqual(operation.stock_line_ids.new_value, 284.01)
        expected = products.cost_currency_id._convert(284.01, orders.currency_id, orders.company_id, day, round=False)
        self.assertAlmostEqual(operation.line_ids.new_cost, expected)
        rate.rate = 0.4
        operation.acknowledge_stock_repair = True
        with self.assertRaisesRegex(UserError, "stale"):
            operation.action_apply()
        operation.action_preview()
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.assertAlmostEqual(issues.value, 284.01)
        self.assertAlmostEqual(orders.lines.total_cost, products.cost_currency_id._convert(
            284.01, orders.currency_id, orders.company_id, day, round=False,
        ))

    def test_separate_acknowledgement_and_reason(self):
        _products, _receipts, orders, issues = self._fixture()
        operation = self._repair(orders)
        operation.allow_zero_cost = True
        with self.assertRaisesRegex(UserError, "Acknowledge"):
            operation.action_apply()
        operation.acknowledge_stock_repair = True
        operation.reason = " "
        with self.assertRaisesRegex(UserError, "reason"):
            operation.action_apply()
        self.assertEqual(issues.value, 0)

    def test_uninstall_without_repairs_uses_standard_path(self):
        module = self.env.ref("base.module_pos_cost_recompute")
        with patch.object(type(self.env["ir.model.data"]), "_module_data_uninstall") as uninstall:
            module.module_uninstall()
        uninstall.assert_called_once_with(["pos_cost_recompute"])

    def test_repair_more_than_1000_shared_lines_without_truncation(self):
        line_count = 1001
        _products, receipts, orders, issues = self._fixture(
            quantities=[line_count], sale_quantities=[line_count],
        )
        line = orders.lines
        line.write({"qty": 1, "price_subtotal": 1000, "price_subtotal_incl": 1000})
        vals = line.copy_data()[0]
        self.env["pos.order.line"].create([dict(vals) for _ in range(line_count - 1)])
        start = perf_counter()
        operation = self._repair(orders)
        elapsed = perf_counter() - start
        self.assertEqual(len(operation.line_ids), line_count)
        self.assertEqual(operation.line_ids.pos_line_id, orders.lines)
        self.assertEqual(operation.stock_repair_count, 1)
        self.assertAlmostEqual(operation.stock_line_ids.new_value, receipts.value)
        evidence_size = len(json.dumps(operation.stock_evidence))
        self.assertLess(evidence_size, 10000)
        operation.acknowledge_stock_repair = True
        apply_start = perf_counter()
        operation.action_apply()
        apply_elapsed = perf_counter() - apply_start
        self.assertAlmostEqual(sum(orders.lines.mapped("total_cost")), receipts.value, places=2)
        self.assertAlmostEqual(issues.value, receipts.value, places=2)
        logging.getLogger(__name__).info(
            "Stock repair: %s POS lines, %s stock issues, preview %.3fs, apply %.3fs, %s evidence bytes",
            line_count, len(issues), elapsed, apply_elapsed, evidence_size,
        )

    def test_repair_with_more_than_10000_history_moves_without_truncation(self):
        products, receipts, orders, issues = self._fixture()
        vals = {"product_id": products.id, "product_uom": products.uom_id.id,
                "product_uom_qty": 1, "location_id": issues.location_id.id,
                "location_dest_id": issues.location_dest_id.id}
        history = self.env["stock.move"].create([dict(vals) for _ in range(9999)])
        start = perf_counter()
        operation = self._repair(orders)
        elapsed = perf_counter() - start
        self.assertEqual(operation.stock_repair_count, 1)
        evidence = operation.stock_evidence[str(products.id)]["moves"]
        self.assertEqual(len(evidence), 10001)
        self.assertEqual({move["id"] for move in evidence}, set((history | receipts | issues).ids))
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.assertEqual(operation.state, "done")
        self.assertAlmostEqual(issues.value, receipts.value)
        self.assertAlmostEqual(orders.lines.total_cost, receipts.value)
        logging.getLogger(__name__).info(
            "Stock repair history: %s movements, preview %.3fs, %s evidence bytes",
            len(evidence), elapsed, len(json.dumps(operation.stock_evidence)),
        )

    def test_company_rules_hidden_history_and_forged_results(self):
        _products, receipts, orders, issues = self._fixture()
        operation = self._repair(orders)
        other = self.env["res.company"].create({"name": "Other repair company"})
        user = new_test_user(
            self.env, login="stock-repair-other-company",
            groups="point_of_sale.group_pos_manager,stock.group_stock_manager",
            company_id=other.id, company_ids=[Command.set(other.ids)],
        )
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            operation.stock_line_ids.with_user(user).with_context(allowed_company_ids=other.ids).read(["new_value"])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            issues.copy({"cost_repair_line_id": operation.stock_line_ids.id})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.env["pos.cost.recompute.stock.line"].with_context(pos_cost_recompute_internal=True).create({})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            operation.write({"stock_evidence": {"forged": True}})
        self.env["ir.rule"].create({
            "name": "Hide one source receipt", "model_id": self.env["ir.model"]._get_id("stock.move"),
            "domain_force": repr([("id", "!=", receipts.id)]),
        })
        with self.assertRaisesRegex(AccessError, "complete stock history"):
            self._repair(orders)

    def test_russian_repair_preview_applies_in_another_language(self):
        self.env["res.lang"]._activate_lang("ru_RU")
        self.env.ref("base.module_pos_cost_recompute")._update_translations(["ru_RU"], overwrite=True)
        label = self.Operation.with_context(lang="ru_RU").fields_get(["repair_stock_values"])["repair_stock_values"]["string"]
        self.assertEqual(label, "Исправить нулевую оценку склада и пересчитать POS")
        _products, _receipts, orders, issues = self._fixture()
        operation = self._operation(orders, preview=False, repair_stock_values=True)
        operation.with_context(lang="ru_RU").action_preview()
        self.assertIn("Историческая оценка", operation.stock_line_ids.warning)
        operation.acknowledge_stock_repair = True
        operation.with_context(lang="en_US").action_apply()
        self.assertAlmostEqual(issues.value, 284.01)

    def test_aggregate_session_source_and_incomplete_delivery(self):
        product = self.create_product("Aggregate zero cost", self.category, 1000, 0)
        self._receipt(product)
        orders = self._orders([(product, 1)], closing=True)
        self.category.property_cost_method = "fifo"
        operation = self._repair(orders)
        self.assertEqual(operation.stock_repair_count, 0)
        self.assertIn("Aggregate session", operation.stock_line_ids.skip_reason)
        self.category.property_cost_method = "standard"
        product.standard_price = 0
        self._receipt(product, day=3)
        direct = self._orders([(product, 1)])
        self.category.property_cost_method = "fifo"
        direct.picking_ids.move_ids.state = "assigned"
        self.assertEqual(self._repair(direct).stock_repair_count, 0)

    def test_pos_and_stock_manager_can_apply_without_settings_rights(self):
        _products, _receipts, orders, issues = self._fixture()
        user = new_test_user(
            self.env, login="stock-repair-manager",
            groups="point_of_sale.group_pos_manager,stock.group_stock_manager",
            company_id=self.env.company.id,
        )
        operation = self._operation(orders, preview=False, repair_stock_values=True).with_user(user)
        operation.action_preview()
        self.assertEqual(operation.stock_repair_count, 1)
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.assertAlmostEqual(issues.value, 284.01)
        self.assertEqual(operation.applied_by_id, user)
