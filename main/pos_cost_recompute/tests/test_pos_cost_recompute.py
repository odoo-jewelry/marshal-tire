from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("post_install", "-at_install")
class TestPosCostRecompute(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.create_product("Cost recomputation product", cls.categ_basic, 60, 40)
        cls.service = cls.create_product("Cost recomputation service", cls.categ_basic, 30, 15)
        cls.service.write({"is_storable": False, "type": "service"})
        cls.adjust_inventory((cls.product,), (100,))
        cls.operator = new_test_user(
            cls.env, login="cost-recompute-cashier", groups="point_of_sale.group_pos_user",
            company_id=cls.env.company.id,
        )
        cls.manager = new_test_user(
            cls.env, login="cost-recompute-manager", groups="point_of_sale.group_pos_manager",
            company_id=cls.env.company.id,
        )

    def setUp(self):
        super().setUp()
        self.config = self.basic_config
        self.Operation = self.env["pos.cost.recompute"]

    def _orders(self, items=None, close=True, closing=False, invoiced=False):
        self.env.company.point_of_sale_update_stock_quantities = "closing" if closing else "real"
        self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        orders = self.env["pos.order"]
        for index, (product, quantity) in enumerate(items or [(self.product, 2)]):
            values = self.create_ui_order_data(
                [(product, quantity)], customer=self.customer, is_invoiced=invoiced,
                payments=[(self.bank_pm1, self.pricelist._get_product_price(product, quantity) * quantity)],
                uuid=f"cost-recompute-{index}-{self.pos_session.id}",
            )
            result = self.env["pos.order"].with_context(generate_pdf=False).sync_from_ui([values])
            orders |= self.env["pos.order"].browse([o["id"] for o in result["pos.order"]])
        if close:
            self.pos_session.post_closing_cash_details(0)
            self.pos_session.close_session_from_ui()
            self.assertEqual(self.pos_session.state, "closed")
        return orders

    def _operation(self, orders, preview=True, **values):
        operation = self.Operation.create({
            "company_id": orders.company_id.id,
            "selection_type": "orders",
            "order_ids": [Command.set(orders.ids)],
            "cost_mode": "all", "reason": "Correct historical costs", **values,
        })
        if preview:
            operation.action_preview()
        return operation

    def _valuation_product(self, method="fifo"):
        category = self.categ_basic.copy({"name": f"Recompute {method}", "property_cost_method": method})
        product = self.create_product(f"Recompute {method}", category, 60, 30)
        self.adjust_inventory((product,), (20,))
        return product

    def test_standard_cost_preview_apply_and_report(self):
        order = self._orders()
        order.lines.write({"total_cost": 0, "is_total_cost_computed": True})
        operation = self._operation(order)
        self.assertEqual(order.lines.total_cost, 0)
        self.assertTrue(order.lines.is_total_cost_computed)
        self.assertEqual(operation.line_ids.new_cost, 80)
        self.assertEqual(operation.changed_count, 1)
        operation.action_apply()
        self.assertEqual(order.lines.total_cost, 80)
        self.assertEqual(order.margin, 40)
        self.env.flush_all()
        report = self.env["report.pos.order"].search([("order_id", "=", order.id)])
        self.assertAlmostEqual(sum(report.mapped("margin")), 40)
        self.assertEqual(operation.line_ids.actual_cost, 80)
        self.assertEqual(operation.applied_by_id, self.env.user)

    def test_zero_and_nonzero_selection(self):
        orders = self._orders([(self.product, 1), (self.service, 1)])
        orders.lines[0].total_cost = 0
        orders.lines[1].total_cost = 999
        operation = self._operation(orders, cost_mode="zero")
        self.assertEqual(operation.line_ids.pos_line_id, orders.lines[0])
        operation.cost_mode = "all"
        self.assertEqual(operation.state, "draft")
        self.assertFalse(operation.line_ids)
        operation.action_preview()
        self.assertEqual(operation.line_ids.pos_line_id, orders.lines)
        operation.action_apply()
        self.assertEqual(orders.lines.mapped("total_cost"), [40, 15])

    def test_completion_marker_only(self):
        order = self._orders()
        order.lines.is_total_cost_computed = False
        operation = self._operation(order)
        self.assertEqual(operation.completion_count, 1)
        operation.action_apply()
        self.assertTrue(order.lines.is_total_cost_computed)
        self.assertEqual(order.lines.total_cost, 80)

    def test_zero_source_acknowledgement(self):
        order = self._orders()
        self.product.standard_price = 0
        operation = self._operation(order)
        self.assertEqual(operation.zero_count, 1)
        with self.assertRaises(UserError):
            operation.action_apply()
        self.assertEqual(order.lines.total_cost, 80)
        operation.allow_zero_cost = True
        operation.action_apply()
        self.assertEqual(order.lines.total_cost, 0)

    def test_service_without_movements(self):
        order = self._orders([(self.service, 2)])
        self.assertFalse(order.picking_ids)
        order.lines.total_cost = 111
        operation = self._operation(order)
        operation.action_apply()
        self.assertEqual(order.lines.total_cost, 30)

    def test_current_cost_return_and_unselected_link(self):
        sale = self._orders([(self.product, 2)])
        refund = self._orders([(self.product, -1)])
        refund.lines.refunded_orderline_id = sale.lines
        refund.lines.total_cost = -999
        sale.lines.total_cost = 0
        operation = self._operation(sale)
        self.assertEqual(operation.line_ids.related_line_ids, refund.lines)
        operation.action_apply()
        self.assertEqual(refund.lines.total_cost, -999)
        self._operation(refund).action_apply()
        self.assertEqual(refund.lines.total_cost, -40)

    def test_fifo_uses_direct_valuation(self):
        product = self._valuation_product()
        orders = self._orders([(product, 2), (product, 1)])
        orders.lines.total_cost = 0
        source = orders[0].picking_ids.move_ids
        expected = source._get_price_unit() * 2
        product.standard_price = 99
        operation = self._operation(orders[0])
        self.assertEqual(operation.line_ids.source, "order_moves")
        self.assertEqual(operation.line_ids.move_ids, source)
        operation.action_apply()
        self.assertAlmostEqual(orders[0].lines.total_cost, expected)
        self.assertEqual(orders[1].lines.total_cost, 0)

    def test_average_uses_full_session_source(self):
        product = self._valuation_product("average")
        orders = self._orders([(product, 1), (product, 3)], closing=True)
        self.assertFalse(orders.picking_ids)
        orders.lines.total_cost = 0
        operation = self._operation(orders[0])
        self.assertEqual(operation.line_ids.source, "session_moves")
        source = self.pos_session.picking_ids.move_ids.filtered(lambda m: m.product_id == product)
        self.assertEqual(operation.line_ids.move_ids, source)
        self.assertEqual(sum(m._get_valued_qty() for m in source), 4)
        operation.action_apply()
        self.assertAlmostEqual(orders[0].lines.total_cost, source._get_price_unit())
        self.assertEqual(orders[1].lines.total_cost, 0)

    def test_mixed_session_directions_are_skipped(self):
        product = self._valuation_product("average")
        orders = self._orders([(product, 2), (product, -1)], closing=True)
        operation = self._operation(orders[:1])
        self.assertEqual(operation.skipped_count, 1)
        self.assertIn("mixes sales and returns", operation.line_ids.skip_reason)
        self.assertFalse(operation.can_apply)

    def test_valued_return_keeps_existing_value(self):
        product = self._valuation_product()
        self._orders([(product, 2)])
        refund = self._orders([(product, -1)])
        moves = refund.picking_ids.move_ids
        value = moves._get_price_unit()
        refund.lines.total_cost = -999
        operation = self._operation(refund)
        operation.action_apply()
        self.assertAlmostEqual(refund.lines.total_cost, -value)

    def test_open_and_closing_sessions_are_skipped(self):
        order = self._orders(close=False, closing=True)
        for state in ("opened", "closing_control"):
            self.pos_session.state = state
            operation = self._operation(order)
            self.assertEqual(operation.skipped_count, 1)
            self.assertIn("not closed", operation.line_ids.skip_reason)

    def test_draft_cancelled_and_zero_quantity(self):
        order = self._orders()
        draft = order.copy({"state": "draft"})
        cancelled = order.copy({"state": "cancel"})
        zero = order.copy({"state": "paid"})
        zero.lines.qty = 0
        operation = self._operation(draft | cancelled | zero)
        self.assertEqual(operation.skipped_count, 3)

    def test_missing_and_incomplete_stock_sources(self):
        product = self._valuation_product()
        order = self._orders([(product, 1)])
        moves = order.picking_ids.move_ids
        moves.state = "assigned"
        operation = self._operation(order)
        self.assertIn("not complete", operation.line_ids.skip_reason)
        order.picking_ids.pos_order_id = False
        operation.action_preview()
        self.assertIn("No provable", operation.line_ids.skip_reason)

    def test_zero_valued_quantity_is_skipped(self):
        product = self._valuation_product()
        order = self._orders([(product, 1)])
        with patch.object(type(order.picking_ids.move_ids), "_get_valued_qty", return_value=0):
            operation = self._operation(order)
        self.assertIn("no positive valued quantity", operation.line_ids.skip_reason)

    def test_deferred_zero_fallback_is_skipped(self):
        product = self._valuation_product()
        order = self._orders([(product, 1)])
        order.shipping_date = fields.Date.today()
        with patch.object(type(order.lines), "_get_product_cost_with_moves", return_value=0):
            operation = self._operation(order)
        self.assertIn("zero-cost substitution", operation.line_ids.skip_reason)

    def test_completed_deferred_delivery(self):
        product = self._valuation_product()
        order = self._orders([(product, 1)])
        order.shipping_date = fields.Date.today()
        order.lines.total_cost = 999
        operation = self._operation(order)
        self.assertEqual(operation.changed_count, 1)
        operation.action_apply()

    def test_archived_product(self):
        order = self._orders()
        self.product.active = False
        order.lines.total_cost = 0
        operation = self._operation(order)
        self.assertEqual(operation.changed_count, 1)
        operation.action_apply()

    def test_period_and_product_intersection(self):
        orders = self._orders([(self.product, 1), (self.service, 1)])
        date = orders[0].date_order
        operation = self.Operation.with_context(tz="Europe/Kyiv").create({
            "company_id": orders.company_id.id, "selection_type": "period",
            "date_from": date, "date_to": date + timedelta(days=1),
            "product_ids": [Command.set(self.service.ids)],
            "config_ids": [Command.set(self.config.ids)], "cost_mode": "all",
        })
        operation.action_preview()
        self.assertEqual(operation.line_ids.product_id, self.service)
        operation.write({"date_from": date - timedelta(days=1), "date_to": date})
        operation.action_preview()
        self.assertFalse(operation.line_ids)

    def test_explicit_selection_never_expands(self):
        orders = self._orders([(self.product, 1), (self.product, 1)])
        operation = self._operation(orders[:1])
        self.assertEqual(operation.line_ids.pos_line_id.order_id, orders[:1])
        self.assertEqual(orders[1].lines.total_cost, 40)

    def test_selection_bound_and_empty(self):
        with self.assertRaises(UserError):
            self.Operation.create({}).action_preview()
        operation = self.Operation.create({"selection_type": "orders"})
        with self.assertRaises(UserError):
            operation.action_preview()
        order = self._orders()
        line_values = order.lines.copy_data()[0]
        line_values["order_id"] = order.id
        self.env["pos.order.line"].create([line_values.copy() for _ in range(1000)])
        operation = self._operation(order, preview=False)
        with self.assertRaisesRegex(UserError, "1000"):
            operation.action_preview()
        order.lines[-1:].product_id = self.service
        operation.product_ids = self.product
        self.assertEqual(len(operation._select_lines()), 1000)
        operation.action_preview()
        self.assertEqual(len(operation.line_ids), 1000)
        operation.action_apply()
        self.assertEqual(operation.state, "done")

    def test_changed_inputs_invalidate_preview(self):
        order = self._orders()
        for record, values in (
            (self.product, {"standard_price": 45}),
            (order.lines, {"qty": 3}),
            (order.lines, {"total_cost": 777}),
            (order.lines, {"is_total_cost_computed": False}),
        ):
            operation = self._operation(order)
            record.write(values)
            before = (order.lines.total_cost, order.lines.is_total_cost_computed)
            with self.assertRaisesRegex(UserError, "stale"):
                operation.action_apply()
            self.assertEqual(operation.state, "ready")
            self.assertEqual((order.lines.total_cost, order.lines.is_total_cost_computed), before)

    def test_runtime_failure_rolls_back_cost_and_history(self):
        orders = self._orders([(self.product, 1), (self.service, 1)])
        orders.lines.total_cost = 0
        operation = self._operation(orders)
        original = type(orders.lines)._compute_total_cost

        def fail_after_first(lines, moves):
            original(lines[:1], moves)
            raise UserError("Test failure after first write")

        with patch.object(type(orders.lines), "_compute_total_cost", fail_after_first):
            with self.assertRaisesRegex(UserError, "Test failure"):
                operation.action_apply()
        self.assertEqual(orders.lines.mapped("total_cost"), [0, 0])
        self.assertEqual(operation.state, "ready")
        self.assertFalse(operation.applied_at)

    def test_retry_overlap_and_unchanged(self):
        order = self._orders()
        order.lines.total_cost = 0
        first = self._operation(order)
        second = self._operation(order)
        first.action_apply()
        applied_at = first.applied_at
        first.action_apply()
        self.assertEqual(first.applied_at, applied_at)
        with self.assertRaisesRegex(UserError, "stale"):
            second.action_apply()
        fresh = self._operation(order)
        self.assertEqual(fresh.unchanged_count, 1)
        before = order.lines.write_date
        fresh.action_apply()
        self.assertEqual(order.lines.write_date, before)

    def test_cancel_and_required_reason(self):
        order = self._orders()
        operation = self._operation(order, reason=" ")
        with self.assertRaisesRegex(UserError, "reason"):
            operation.action_apply()
        operation.action_cancel()
        with self.assertRaises(UserError):
            operation.action_apply()
        with self.assertRaises(UserError):
            operation.reason = "Changed"

    def test_access_and_history_forgery(self):
        order = self._orders()
        with self.assertRaises(AccessError):
            self.Operation.with_user(self.operator).create({})
        operation = self._operation(order)
        with self.assertRaises(AccessError):
            operation.with_user(self.operator).action_apply()
        with self.assertRaises(AccessError):
            self.Operation.create({"state": "done"})
        with self.assertRaises(AccessError):
            operation.line_ids.new_cost = 1
        with self.assertRaises(AccessError):
            operation.with_context(pos_cost_recompute_internal=True).write({"state": "done"})
        operation.action_apply()
        for action in (lambda: operation.write({"reason": "forged"}), operation.unlink,
                       lambda: operation.line_ids.unlink()):
            with self.assertRaises(UserError):
                action()
        copied = operation.copy()
        self.assertEqual(copied.state, "draft")
        self.assertFalse(copied.line_ids)
        self.assertFalse(copied.reason)
        forged_default = self.Operation.with_context(default_state="done", default_applied_at=fields.Datetime.now()).create({})
        self.assertEqual(forged_default.state, "draft")
        self.assertFalse(forged_default.applied_at)

    def test_manager_and_source_access(self):
        order = self._orders()
        operation = self._operation(order).with_user(self.manager)
        operation.action_preview()
        rule = self.env["ir.rule"].create({
            "name": "Block test cost source", "model_id": self.env["ir.model"]._get_id("product.product"),
            "domain_force": str([("id", "!=", self.product.id)]),
        })
        with self.assertRaises(AccessError):
            operation.action_apply()
        self.assertEqual(operation.state, "ready")
        rule.unlink()

    def test_company_isolation(self):
        order = self._orders()
        other = self.env["res.company"].create({"name": "Cost Recompute Other Company"})
        with self.assertRaises(UserError):
            self.Operation.with_user(self.manager).create({"company_id": other.id})
        with self.assertRaises(UserError):
            self.Operation.with_context(allowed_company_ids=[self.env.company.id, other.id]).create({
                "company_id": other.id, "selection_type": "orders",
                "order_ids": [Command.set(order.ids)],
            })

    def test_operational_data_unchanged(self):
        order = self._orders(invoiced=True)
        order.lines.total_cost = 0
        moves = order.picking_ids.move_ids
        invoices = order.account_move | order.session_id.move_id
        before = {
            "orders": order.read(["state", "amount_total", "amount_tax", "amount_paid", "amount_return"]),
            "lines": order.lines.read(["qty", "price_unit", "discount", "tax_ids", "price_subtotal"]),
            "payments": order.payment_ids.read(["amount", "payment_method_id"]),
            "moves": moves.read(["quantity", "value", "state"]),
            "account": invoices.line_ids.read(["debit", "credit", "amount_currency"]),
            "price": self.product.standard_price,
        }
        self._operation(order).action_apply()
        self.assertEqual(order.read(["state", "amount_total", "amount_tax", "amount_paid", "amount_return"]), before["orders"])
        self.assertEqual(order.lines.read(["qty", "price_unit", "discount", "tax_ids", "price_subtotal"]), before["lines"])
        self.assertEqual(order.payment_ids.read(["amount", "payment_method_id"]), before["payments"])
        self.assertEqual(moves.read(["quantity", "value", "state"]), before["moves"])
        self.assertEqual(invoices.line_ids.read(["debit", "credit", "amount_currency"]), before["account"])
        self.assertEqual(self.product.standard_price, before["price"])

    def test_ordinary_flow_without_operation(self):
        before = self.Operation.search_count([])
        sale = self._orders()
        self.assertEqual(sale.lines.total_cost, 80)
        self.assertTrue(sale.lines.is_total_cost_computed)
        refund = self._orders([(self.product, -1)])
        self.assertEqual(refund.lines.total_cost, -40)
        self.assertEqual(self.Operation.search_count([]), before)

    def test_currency_uses_order_date_and_stale_rate(self):
        self.config = self.other_currency_config
        original_bank, original_cash = self.bank_pm1, self.cash_pm1
        self.bank_pm1, self.cash_pm1 = self.bank_pm2, self.cash_pm2
        order = self._orders([(self.service, 2)])
        self.bank_pm1, self.cash_pm1 = original_bank, original_cash
        date = fields.Date.today() - timedelta(days=10)
        rate = self.env["res.currency.rate"].create({
            "currency_id": self.other_currency.id, "company_id": self.env.company.id,
            "name": date, "rate": 0.25,
        })
        order.date_order = fields.Datetime.to_datetime(date)
        order.lines.total_cost = 999
        operation = self._operation(order)
        expected = self.service.cost_currency_id._convert(
            30, order.currency_id, order.company_id, date, round=False
        )
        self.assertAlmostEqual(operation.line_ids.new_cost, expected)
        rate.rate = 0.4
        with self.assertRaisesRegex(UserError, "stale"):
            operation.action_apply()
        operation.action_preview()
        operation.action_apply()
        self.assertAlmostEqual(order.lines.total_cost, self.service.cost_currency_id._convert(
            30, order.currency_id, order.company_id, date, round=False
        ))

    def test_valuation_change_invalidates_preview(self):
        product = self._valuation_product()
        order = self._orders([(product, 1)])
        operation = self._operation(order)
        order.picking_ids.move_ids.value = 37
        with self.assertRaisesRegex(UserError, "stale"):
            operation.action_apply()

    def test_new_source_invalidates_preview(self):
        product = self._valuation_product()
        order = self._orders([(product, 1)])
        operation = self._operation(order)
        order.picking_ids.move_ids.copy({"state": "assigned"})
        with self.assertRaisesRegex(UserError, "stale"):
            operation.action_apply()

    def test_applied_history_survives_source_changes(self):
        order = self._orders()
        operation = self._operation(order)
        operation.action_apply()
        snapshot = operation.line_ids.snapshot
        self.product.standard_price = 17
        self.assertEqual(operation.line_ids.snapshot, snapshot)
        self.assertEqual(operation.line_ids.actual_cost, 80)

    def test_changed_price_precision_invalidates_preview(self):
        order = self._orders()
        operation = self._operation(order)
        precision = self.env["decimal.precision"].search([("name", "=", "Product Price")])
        precision.digits += 1
        with self.assertRaisesRegex(UserError, "stale"):
            operation.action_apply()

    def test_combo_and_project_correction_detection(self):
        orders = self._orders([(self.product, 1), (self.product, 1)])
        orders[1].lines.combo_parent_id = orders[0].lines
        operation = self._operation(orders)
        self.assertEqual(operation.skipped_count, 2)
        self.assertTrue(all("combo" in detail.skip_reason for detail in operation.line_ids))
        orders[1].lines.combo_parent_id = False
        if "pos.order.correction" not in self.env:
            self.skipTest("The optional project correction module is not installed.")
        self.env.user.group_ids |= self.env.ref("pos_order_correction.group_pos_order_correction")
        self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        orders[0].action_prepare_correction()
        operation.action_preview()
        self.assertEqual(operation.skipped_count, 1)
        self.assertEqual(operation.line_ids.filtered(lambda line: line.status == "skipped").order_id, orders[0])

    def test_product_cost_reads_order_company(self):
        order = self._orders()
        other = self.env["res.company"].create({"name": "Different Cost Company"})
        self.product.company_id = False
        self.product.with_company(other).standard_price = 987
        operation = self._operation(order, preview=False)
        self.env.user.company_ids |= other
        operation.with_context(allowed_company_ids=[other.id, order.company_id.id]).action_preview()
        self.assertEqual(operation.line_ids.new_cost, 80)

    def test_manager_can_apply_and_history_action(self):
        order = self._orders()
        order.lines.total_cost = 0
        action = order.with_user(self.manager).action_prepare_cost_recompute()
        operation = self.Operation.browse(action["res_id"]).with_user(self.manager)
        operation.reason = "Manager correction"
        operation.action_preview()
        operation.action_apply()
        self.assertEqual(operation.applied_by_id, self.manager)
        self.assertEqual(order.lines.total_cost, 80)
        history = order.with_user(self.manager).action_view_cost_recomputations()
        self.assertIn(operation, self.Operation.search(history["domain"]))

    def test_russian_translation_and_cross_language_preview(self):
        self.env["res.lang"]._activate_lang("ru_RU")
        self.env["ir.module.module"].search([
            ("name", "=", "pos_cost_recompute")
        ])._update_translations(["ru_RU"], overwrite=True)
        translated = self.Operation.with_context(lang="ru_RU")
        labels = dict(translated.fields_get(["state"])["state"]["selection"])
        self.assertEqual(labels["done"], "Применено")
        order = self._orders()
        operation = self._operation(order)
        operation.with_context(lang="ru_RU").action_apply()
        self.assertEqual(operation.state, "done")

    def test_shared_source_affected_by_project_correction(self):
        if "pos.order.correction" not in self.env:
            self.skipTest("The optional project correction module is not installed.")
        product = self._valuation_product("average")
        orders = self._orders([(product, 1), (product, 2)], closing=True)
        self.env.user.group_ids |= self.env.ref("pos_order_correction.group_pos_order_correction")
        self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        orders[0].action_prepare_correction()
        operation = self._operation(orders[1])
        self.assertEqual(operation.skipped_count, 1)
        self.assertIn("shared session source", operation.line_ids.skip_reason)

    def test_kit_exclusion_when_mrp_available(self):
        if "mrp.bom" not in self.env:
            self.skipTest("The optional manufacturing module is not installed.")
        order = self._orders()
        self.env["mrp.bom"].create({
            "product_tmpl_id": self.product.product_tmpl_id.id, "type": "phantom",
            "bom_line_ids": [Command.create({"product_id": self.service.id, "product_qty": 1})],
        })
        operation = self._operation(order)
        self.assertIn("Manufacturing kits", operation.line_ids.skip_reason)
