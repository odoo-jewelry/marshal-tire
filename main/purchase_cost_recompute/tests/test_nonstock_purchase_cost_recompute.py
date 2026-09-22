from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from ..models.product_product import _CONTEXT_KEY, _INTERNAL
from .common import PurchaseCostRecomputeCommon


@tagged("post_install", "-at_install")
class TestNonstockPurchaseCostRecompute(PurchaseCostRecomputeCommon):
    def _snapshot(self, orders):
        products = orders.order_line.product_id
        domain = [("product_id", "in", products.ids),
                  ("company_id", "in", orders.company_id.ids)]
        moves = self.env["stock.move"].search(domain, order="id")
        quants = self.env["stock.quant"].search(domain, order="id")
        pos_lines = self.env["pos.order.line"].search(domain, order="id")
        return (
            orders.order_line.read(["price_unit", "discount", "product_qty", "tax_ids"]),
            moves.read(["value", "quantity", "date", "state", "origin_returned_move_id"]),
            quants.read(["quantity", "reserved_quantity", "location_id"]),
            products.read(["standard_price", "qty_available", "is_storable"]),
            pos_lines.read(["total_cost", "is_total_cost_computed", "margin"]),
        )

    def _assert_rejected(self, orders, reason=None, error=UserError):
        before = self._snapshot(orders)
        with self.assertRaises(error) as failure:
            orders._apply_purchase_cost_recompute()
        self.assertEqual(self._snapshot(orders), before)
        if reason:
            self.assertIn(reason, str(failure.exception))
        return str(failure.exception)

    def test_ordinary_nonstock_pos_uses_current_cost_despite_historical_moves(self):
        self._purchase(quantity=2)
        sale = self._pos_order()
        self._purchase(price=200, quantity=3, taxes=self.env["account.tax"],
                       date="2026-01-03 10:00:00")
        moves = sale.picking_ids.move_ids
        self.assertEqual(moves.value, 100)
        self.product.write({"is_storable": False, "standard_price": 777})
        sale.lines.is_total_cost_computed = False
        sale.lines._compute_total_cost(moves)
        self.assertEqual(sale.lines.total_cost, 777)
        self.assertEqual(sale.margin, 200 - 777)
        self.assertFalse(self.product.is_storable)
        self.assertEqual(moves.value, 100)

    def test_package_receipt_uses_existing_history_without_changing_physical_facts(self):
        order = self._purchase(price=10, quantity=50)
        receipt = order.order_line.move_ids
        self.product.is_storable = False
        facts = receipt.read(["quantity", "date", "state", "move_line_ids", "purchase_line_id"])
        quants = self.env["stock.quant"].search([("product_id", "=", self.product.id)])
        quantities = quants.read(["quantity", "reserved_quantity", "location_id"])
        self.assertEqual(receipt.value, 500)
        self.assertEqual(self.product.qty_available, 50)
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 12)
        self.assertFalse(order.order_line.tax_ids)
        self.assertEqual(receipt.value, 600)
        self.assertEqual(self.product.standard_price, 12)
        self.assertFalse(self.product.is_storable)
        self.assertEqual(self.product.qty_available, 50)
        self.assertEqual(receipt.read(list(facts[0].keys())), facts)
        self.assertEqual(quants.read(["quantity", "reserved_quantity", "location_id"]), quantities)
        self.assertEqual((result["purchase_lines"], result["receipts"]), (1, 1))

    def test_mixed_selection_rounds_prices_preserves_discounts_and_repeats_as_noop(self):
        other = self.create_product("Tracked mixed purchase product", self.category, 200, 100)
        nonstock = self._purchase(price=27.33, discount=10)
        tracked = self._purchase(price=20, quantity=3, product=other,
                                 date="2026-01-02 10:00:00")
        self.product.is_storable = False
        orders = nonstock | tracked
        result = orders._apply_purchase_cost_recompute()
        self.assertEqual((result["purchase_lines"], result["receipts"]), (2, 2))
        self.assertEqual(nonstock.order_line.price_unit, 32.80)
        self.assertEqual(nonstock.order_line.discount, 10)
        self.assertAlmostEqual(nonstock.order_line.move_ids.value, 59.04)
        self.assertEqual(tracked.order_line.price_unit, 24)
        self.assertEqual(tracked.order_line.move_ids.value, 72)
        self.assertFalse(orders.order_line.tax_ids)
        self.assertFalse(self.product.is_storable)
        self.assertTrue(other.is_storable)
        before = self._snapshot(orders)
        result = orders._apply_purchase_cost_recompute()
        self.assertEqual(result["purchase_lines"], 0)
        self.assertEqual(result["receipts"], 0)
        self.assertEqual(self._snapshot(orders), before)

    def test_half_cent_rounds_up_for_nonstock_goods(self):
        tax = self.tax.copy({"name": "Nonstock half cent", "amount": 50})
        order = self._purchase(price=0.03, taxes=tax)
        self.product.is_storable = False
        order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 0.05)
        self.assertEqual(order.order_line.move_ids.value, 0.10)

    def test_unit_and_advance_diagnostics_identify_order_and_product(self):
        order = self._purchase()
        self.product.is_storable = False
        for values, reason in (
            ({"product_uom_id": self.env.ref("uom.product_uom_dozen").id}, "base unit"),
            ({"is_downpayment": True}, "advance payments"),
        ):
            with self.subTest(values=values), self.env.cr.savepoint() as savepoint:
                order.order_line.write(values)
                message = self._assert_rejected(order, reason)
                self.assertIn(order.display_name, message)
                self.assertIn(self.product.display_name, message)
                self.assertNotIn("stocked products", message)
                savepoint.rollback()

    def test_service_line_rejects_the_entire_mixed_selection(self):
        goods = self._purchase()
        self.product.is_storable = False
        service = self.create_product("Correction service", self.category, 200, 100)
        service.write({"type": "service", "is_storable": False})
        service_order = self._purchase(product=service, receive=False,
                                       date="2026-01-02 10:00:00")
        message = self._assert_rejected(goods | service_order, "goods")
        self.assertIn(service_order.display_name, message)
        self.assertIn(service.display_name, message)

    def test_missing_and_partial_receipts_explain_the_required_evidence(self):
        order = self._purchase(receive=False)
        self.product.is_storable = False
        for received in (0, 1):
            with self.subTest(received=received):
                if received:
                    moves = order.order_line.move_ids
                    moves.quantity = received
                    moves.picked = True
                    moves._action_done()
                message = self._assert_rejected(order, "fully received")
                self.assertIn(order.display_name, message)
                self.assertIn(self.product.display_name, message)

    def test_completed_nonstock_receipt_without_quants_is_not_a_fifo_basis(self):
        self.product.is_storable = False
        order = self._purchase()
        self.assertEqual(order.order_line.qty_received, 2)
        self.assertEqual(self.product.qty_available, 0)
        message = self._assert_rejected(order, "do not reconcile")
        self.assertIn(self.product.display_name, message)

    def test_later_nonstock_movement_leaves_stale_quants_and_rejects_mixed_batch(self):
        order = self._purchase()
        other = self.create_product("Unaffected tracked product", self.category, 200, 100)
        tracked = self._purchase(product=other, date="2026-01-02 10:00:00")
        self.product.is_storable = False
        issue = self._move(1, "2026-01-03 10:00:00")
        self.assertEqual(issue.state, "done")
        self.assertEqual(self.product.qty_available, 2)
        message = self._assert_rejected(order | tracked, "do not reconcile")
        self.assertIn(self.product.display_name, message)

    def test_nonstock_fifo_preserves_the_order_of_different_receipt_costs(self):
        corrected = self._purchase(quantity=1)
        first_issue = self._move(1, "2026-01-02 10:00:00")
        future = self._purchase(price=200, quantity=2, taxes=self.env["account.tax"],
                                date="2026-01-03 10:00:00")
        second_issue = self._move(1, "2026-01-04 10:00:00")
        self.product.write({"is_storable": False, "standard_price": 777})
        moves = corrected.order_line.move_ids | future.order_line.move_ids | first_issue | second_issue
        facts = moves.read(["quantity", "date", "state", "origin_returned_move_id"])
        future_before = future.order_line.read(["price_unit", "tax_ids"])
        corrected._apply_purchase_cost_recompute()
        self.assertEqual(first_issue.value, 120)
        self.assertEqual(second_issue.value, 200)
        self.assertEqual(future.order_line.move_ids.value, 400)
        self.assertEqual(future.order_line.read(["price_unit", "tax_ids"]), future_before)
        self.assertEqual(moves.read(["quantity", "date", "state", "origin_returned_move_id"]), facts)
        self.assertEqual(self.product.qty_available, 1)
        self.assertEqual(self.product.standard_price, 200)
        self.assertFalse(self.product.is_storable)

    def test_direct_sale_and_refund_use_history_instead_of_later_receipt_cost(self):
        purchase = self._purchase()
        sale = self._pos_order()
        refund = self._pos_order(quantity=-1, date="2026-01-03 10:00:00", refund_line=sale.lines)
        self._purchase(price=200, quantity=3, taxes=self.env["account.tax"],
                       date="2026-01-04 10:00:00")
        self.product.write({"is_storable": False, "standard_price": 777})
        orders = sale | refund
        moves = orders.picking_ids.move_ids
        orders.lines.is_total_cost_computed = False
        orders.lines._compute_total_cost(moves)
        self.assertEqual(sale.lines.total_cost, 777)
        self.assertEqual(refund.lines.total_cost, -777)
        fields = ["amount_total", "amount_paid", "amount_tax", "state", "date_order", "payment_ids"]
        facts = orders.read(fields)
        payments = orders.payment_ids.read(["amount", "payment_date", "payment_method_id"])
        stock = moves.read(["quantity", "date", "state", "origin_returned_move_id"])
        result = purchase._apply_purchase_cost_recompute()
        self.assertEqual((sale.lines.total_cost, refund.lines.total_cost), (120, -120))
        self.assertEqual((sale.margin, refund.margin), (80, -80))
        self.assertNotEqual(self.product.standard_price, 120)
        self.assertEqual(result["pos_lines"], 2)
        self.assertEqual(self.pos_session.state, "opened")
        self.assertEqual(orders.read(fields), facts)
        self.assertEqual(orders.payment_ids.read(["amount", "payment_date", "payment_method_id"]), payments)
        self.assertEqual(moves.read(["quantity", "date", "state", "origin_returned_move_id"]), stock)
        self.assertFalse(self.product.is_storable)

    def test_earlier_sale_is_preserved_when_its_later_refund_is_recomputed(self):
        self._purchase(price=90, quantity=2, taxes=self.env["account.tax"])
        sale = self._pos_order(quantity=2)
        corrected = self._purchase(date="2026-01-03 10:00:00")
        refund = self._pos_order(quantity=-1, date="2026-01-04 10:00:00", refund_line=sale.lines)
        self.product.write({"is_storable": False, "standard_price": 777})
        before = (sale.picking_ids.move_ids.value, sale.lines.total_cost)
        result = corrected._apply_purchase_cost_recompute()
        self.assertEqual(before, (180, 180))
        self.assertEqual((sale.picking_ids.move_ids.value, sale.lines.total_cost), before)
        self.assertEqual(refund.picking_ids.move_ids.value, 90)
        self.assertEqual(refund.lines.total_cost, -90)
        self.assertEqual(result["pos_lines"], 1)

    def test_closed_shared_source_updates_every_nonstock_line_without_revenue_changes(self):
        purchase = self._purchase(quantity=5)
        self.company.point_of_sale_update_stock_quantities = "closing"
        first = self._pos_order(quantity=1)
        second = self._pos_order(quantity=3, date="2026-01-02 11:00:00")
        self._close_pos_session()
        self._purchase(price=200, quantity=3, taxes=self.env["account.tax"],
                       date="2026-01-04 10:00:00")
        self.product.is_storable = False
        self.assertFalse((first | second).picking_ids)
        account_lines = self.pos_session.move_id.line_ids
        accounting = account_lines.read(["balance", "debit", "credit", "account_id"])
        result = purchase._apply_purchase_cost_recompute()
        self.assertEqual((first.lines.total_cost, second.lines.total_cost), (120, 360))
        self.assertEqual((first.margin, second.margin), (80, 240))
        self.assertEqual(result["pos_lines"], 2)
        self.assertEqual(self.pos_session.state, "closed")
        self.assertEqual(account_lines.read(["balance", "debit", "credit", "account_id"]), accounting)

    def test_missing_and_incomplete_pos_sources_reject_without_falling_back(self):
        purchase = self._purchase()
        sale = self._pos_order()
        self.product.write({"is_storable": False, "standard_price": 777})
        picking = sale.picking_ids
        with self.env.cr.savepoint() as savepoint:
            picking.pos_order_id = False
            message = self._assert_rejected(purchase, "Cannot recompute POS order")
            self.assertIn(sale.display_name, message)
            savepoint.rollback()
        with self.env.cr.savepoint() as savepoint:
            sale.lines.qty = 2
            self._assert_rejected(purchase, "cannot be fully attributed")
            savepoint.rollback()
        with self.env.cr.savepoint() as savepoint:
            picking.move_ids.state = "assigned"
            self._assert_rejected(purchase, "pending stock movements")
            savepoint.rollback()

    def test_unsupported_shared_returns_remain_rejected(self):
        purchase = self._purchase(quantity=5)
        self.company.point_of_sale_update_stock_quantities = "closing"
        sale = self._pos_order(quantity=2)
        self._pos_order(quantity=-1, date="2026-01-02 11:00:00", refund_line=sale.lines)
        self._close_pos_session()
        self.product.is_storable = False
        self._assert_rejected(purchase, "Unsupported receipt, return or transfer")

    def test_ambiguous_pos_sources_with_consistent_stock_history_remain_rejected(self):
        purchase = self._purchase()
        sale = self._pos_order()
        refund = self._pos_order(quantity=-1, date="2026-01-03 10:00:00", refund_line=sale.lines)
        self.product.is_storable = False
        # The movements remain valid; the POS association no longer identifies
        # a single direction from which the sale can obtain its unit cost.
        refund.picking_ids.pos_order_id = sale
        self._assert_rejected(purchase, "its cost is ambiguous")

    def test_opening_and_cancelling_do_not_change_nonstock_business_values(self):
        order = self._purchase()
        self.product.is_storable = False
        before = self._snapshot(order)
        action = order.action_open_cost_recompute()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual(wizard.order_ids, order)
        self.assertEqual(self._snapshot(order), before)
        wizard.unlink()
        self.assertEqual(self._snapshot(order), before)

    def test_late_pos_failure_rolls_back_mixed_correction_before_retry(self):
        order = self._purchase()
        sale = self._pos_order()
        other = self.create_product("Tracked rollback product", self.category, 200, 100)
        tracked = self._purchase(product=other, date="2026-01-03 10:00:00")
        self.product.is_storable = False
        orders = order | tracked
        before = self._snapshot(orders)
        original = type(sale.lines)._compute_total_cost

        def fail_after_cost_update(lines, moves):
            original(lines, moves)
            self.assertEqual(orders.order_line.mapped("price_unit"), [120, 120])
            self.assertEqual(sale.picking_ids.move_ids.value, 120)
            self.assertEqual(sale.lines.total_cost, 120)
            raise UserError("Failure after nonstock POS cost update")

        with patch.object(type(sale.lines), "_compute_total_cost", fail_after_cost_update):
            self._assert_rejected(orders, "Failure after nonstock POS cost update")
        self.assertEqual(self._snapshot(orders), before)
        result = orders._apply_purchase_cost_recompute()
        self.assertEqual(result["purchase_lines"], 2)
        self.assertEqual(sale.lines.total_cost, 120)
        self.assertFalse(self.product.is_storable)
        self.assertTrue(other.is_storable)

    def test_historical_pos_scope_requires_internal_token_company_and_exact_lines(self):
        self._purchase(quantity=3)
        first = self._pos_order()
        second = self._pos_order(date="2026-01-02 11:00:00")
        other = self.env["res.company"].create({
            "name": "Nonstock context other company", "currency_id": self.company.currency_id.id,
        })
        self.env.user.company_ids |= other
        self.product.write({"is_storable": False, "standard_price": 777})
        moves = first.picking_ids.move_ids
        trusted = {
            "allowed_company_ids": self.company.ids,
            _CONTEXT_KEY: _INTERNAL,
            "_purchase_cost_recompute_company_id": self.company.id,
            "_purchase_cost_recompute_pos_line_ids": tuple(first.lines.ids),
        }
        invalid = [
            {_CONTEXT_KEY: True},
            {_CONTEXT_KEY: "purchase_cost_recompute_internal"},
            {"_purchase_cost_recompute_pos_line_ids": ()},
            {"_purchase_cost_recompute_pos_line_ids": tuple(second.lines.ids)},
            {"_purchase_cost_recompute_company_id": False},
            {"_purchase_cost_recompute_company_id": other.id},
            {"allowed_company_ids": (self.company | other).ids},
        ]
        for overrides in invalid:
            with self.subTest(overrides=overrides):
                first.lines.is_total_cost_computed = False
                first.lines.with_context({**trusted, **overrides})._compute_total_cost(moves)
                self.assertEqual(first.lines.total_cost, 777)
        lines = (first | second).lines
        lines.is_total_cost_computed = False
        lines.with_context(trusted)._compute_total_cost(moves)
        self.assertEqual(first.lines.total_cost, 100)
        self.assertEqual(second.lines.total_cost, 777)
        first.lines.is_total_cost_computed = False
        first.lines._compute_total_cost(moves)
        self.assertEqual(first.lines.total_cost, 777)

    def test_nonstock_access_checks_include_hidden_moves_and_pos_lines(self):
        purchase = self._purchase()
        sale = self._pos_order()
        self.product.is_storable = False
        user = new_test_user(
            self.env, login="nonstock-complete-manager",
            groups="purchase.group_purchase_manager,stock.group_stock_manager,"
                   "point_of_sale.group_pos_manager,product.group_product_manager",
            company_id=self.company.id,
        )
        before = self._snapshot(purchase)
        for record in (purchase.order_line.move_ids, sale.lines):
            for read in (True, False):
                with self.subTest(model=record._name, read=read):
                    rule = self.env["ir.rule"].create({
                        "name": "Hide nonstock correction evidence",
                        "model_id": self.env["ir.model"]._get(record._name).id,
                        "domain_force": f"[('id', '!=', {record.id})]",
                        "perm_read": read, "perm_write": not read,
                        "perm_create": False, "perm_unlink": False,
                    })
                    try:
                        with self.assertRaises(AccessError):
                            purchase.with_user(user)._apply_purchase_cost_recompute()
                    finally:
                        # Remove the rule through ORM so rule caches are also
                        # cleared before the full-history snapshot and retry.
                        rule.unlink()
                    self.assertEqual(self._snapshot(purchase), before)
        result = purchase.with_user(user)._apply_purchase_cost_recompute()
        self.assertEqual(result["purchase_lines"], 1)
        self.assertEqual(sale.lines.total_cost, 120)

    def test_nonstock_action_does_not_elevate_missing_manager_or_pos_rights(self):
        purchase = self._purchase()
        self._pos_order()
        self.product.is_storable = False
        before = self._snapshot(purchase)
        for index, groups in enumerate((
            "purchase.group_purchase_manager",
            "stock.group_stock_manager",
            "purchase.group_purchase_manager,stock.group_stock_manager,product.group_product_manager",
        )):
            user = new_test_user(self.env, login=f"nonstock-limited-{index}", groups=groups,
                                 company_id=self.company.id)
            with self.subTest(groups=groups), self.assertRaises(AccessError):
                purchase.with_user(user)._apply_purchase_cost_recompute()
            self.assertEqual(self._snapshot(purchase), before)

    def test_nonstock_shared_product_cost_remains_isolated_by_company(self):
        other = self.env["res.company"].create({
            "name": "Nonstock valuation other company", "currency_id": self.company.currency_id.id,
            "inventory_valuation": "periodic",
        })
        self.env.user.company_ids |= other
        self.product.company_id = False
        self.category.with_company(other).property_cost_method = "fifo"
        own = self._purchase()
        issue = self._move(1, "2026-01-02 10:00:00")
        foreign = self._purchase(price=900, quantity=5, taxes=self.env["account.tax"],
                                 date="2026-01-03 10:00:00", company=other)
        self.product.is_storable = False
        foreign_product = self.product.with_company(other).with_context(allowed_company_ids=other.ids)
        foreign_before = (foreign_product.standard_price, foreign_product.qty_available,
                          foreign.order_line.move_ids.value)
        mixed = (own | foreign).with_context(allowed_company_ids=(self.company | other).ids)
        self._assert_rejected(mixed, "one allowed company", AccessError)
        own.with_context(allowed_company_ids=(self.company | other).ids)._apply_purchase_cost_recompute()
        self.assertEqual(issue.value, 120)
        self.assertEqual(self.product.standard_price, 120)
        self.assertEqual((foreign_product.standard_price, foreign_product.qty_available,
                          foreign.order_line.move_ids.value), foreign_before)

    def test_nonstock_ordinary_writes_copy_and_import_do_not_recompute_history(self):
        purchase = self._purchase()
        sale = self._pos_order()
        self.product.is_storable = False
        before = (sale.picking_ids.move_ids.value, sale.lines.total_cost)
        purchase.order_line.price_unit = 150
        self.assertEqual(purchase.order_line.move_ids.value, 300)
        copied = purchase.copy()
        self.assertEqual(copied.order_line.price_unit, 150)
        self.assertEqual(copied.order_line.tax_ids, self.tax)
        result = self.env["purchase.order.line"].load(
            [".id", "price_unit"], [[str(purchase.order_line.id), "160"]],
        )
        self.assertFalse([message for message in result["messages"] if message["type"] == "error"], result)
        self.assertEqual(purchase.order_line.price_unit, 160)
        self.assertEqual(purchase.order_line.move_ids.value, 320)
        self.assertEqual((sale.picking_ids.move_ids.value, sale.lines.total_cost), before)
        self.assertEqual(purchase.order_line.tax_ids, self.tax)
        self.assertFalse(self.product.is_storable)

    def test_nonstock_financial_and_manual_valuation_protections_remain(self):
        purchase = self._purchase()
        sale = self._pos_order()
        self.product.is_storable = False
        with self.env.cr.savepoint() as savepoint:
            self.company.purchase_lock_date = "2026-01-02"
            self._assert_rejected(purchase, "locked or closed")
            savepoint.rollback()
        with self.env.cr.savepoint() as savepoint:
            purchase.order_line.move_ids.value_manual = 201
            self._assert_rejected(purchase, "manually adjusted")
            savepoint.rollback()
        with self.env.cr.savepoint() as savepoint:
            invoice = self.env["account.move"].create({
                "move_type": "out_invoice", "partner_id": self.customer.id,
                "invoice_line_ids": [Command.create({
                    "product_id": self.product.id, "quantity": 1, "price_unit": 200,
                })],
            })
            sale.account_move = invoice
            purchase._apply_purchase_cost_recompute()
            self.assertEqual(sale.lines.total_cost, 120)
            self.assertEqual(invoice.state, "draft")
            savepoint.rollback()
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.vendor.id,
            "invoice_date": "2026-01-02",
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "quantity": 2, "price_unit": 100,
                "purchase_line_id": purchase.order_line.id,
                "tax_ids": [Command.set(self.tax.ids)],
            })],
        })
        self._assert_rejected(purchase, "vendor bill")
        bill.action_post()
        self._assert_rejected(purchase, "vendor bill")

    def test_nonstock_prior_protected_repair_is_preserved(self):
        purchase = self._purchase()
        sale = self._pos_order()
        self._close_pos_session()
        move = sale.picking_ids.move_ids
        move.value = 0
        operation = self.env["pos.cost.recompute"].create({
            "selection_type": "orders", "order_ids": [Command.set(sale.ids)],
            "cost_mode": "all", "reason": "Preserve repair after tracking is disabled",
            "repair_stock_values": True,
        })
        operation.action_preview()
        self.assertEqual(operation.stock_repair_count, 1, operation.stock_line_ids.mapped("skip_reason"))
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.product.is_storable = False
        evidence = operation.stock_line_ids.read(["move_id", "new_value", "actual_value"])
        self._assert_rejected(purchase, "protected previous cost correction")
        self.assertEqual(operation.state, "done")
        self.assertEqual(operation.stock_line_ids.read(["move_id", "new_value", "actual_value"]), evidence)

    def test_nonstock_stock_only_consolidation_remains_unsupported(self):
        if "merged_into_id" not in self.product.product_tmpl_id._fields:
            self.skipTest("The optional product consolidation module is not installed.")
        self.env.user.group_ids |= self.env.ref(
            "product_card_consolidation.group_product_consolidation_manager"
        )
        merged = self.create_product("Merged source product", self.category, 200, 100)
        merged.product_tmpl_id.action_consolidate_into(self.product.product_tmpl_id)
        self.assertEqual(merged.product_tmpl_id.merged_into_id, self.product.product_tmpl_id)
        purchase = self._purchase()
        self.product.is_storable = False
        self._assert_rejected(purchase, "requires proven full history consolidation")
