from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import BaseCase, new_test_user, tagged
from odoo.tools.translate import code_translations, get_translation

from .common import PurchaseCostRecomputeCommon


@tagged("post_install", "-at_install")
class TestPurchaseCostTranslations(BaseCase):
    def test_nonstock_diagnostics_load_and_format_named_order_and_product(self):
        sources = (
            "%(order)s, %(product)s: purchase lines must contain goods and must not be advance payments.",
            "%(order)s, %(product)s: the purchase unit must match the product base unit.",
            "%(order)s, %(product)s: the purchase line must be fully received.",
            "%(order)s, %(product)s: a completed receipt is required to prove historical cost.",
            "%(product)s requires goods without lot/serial tracking, FIFO and periodic valuation.",
        )
        values = {"order": "P00001", "product": "Package"}
        with patch.dict(code_translations.python_translations, clear=True):
            translations = code_translations.get_python_translations("purchase_cost_recompute", "ru_RU")
            for source in sources:
                with self.subTest(source=source):
                    self.assertIn(source, translations)
                    translated = get_translation("purchase_cost_recompute", "ru_RU", source, values)
                    self.assertNotEqual(translated, source % values)
                    self.assertIn(values["product"], translated)
                    if "%(order)s" in source:
                        self.assertIn(values["order"], translated)
                    self.assertNotIn("%(", translated)

    def test_russian_code_translation_loads_and_formats_named_product(self):
        source = "%(product)s requires proven full history consolidation; absorbed cards still have history or lack consolidation evidence."
        product = "Translation test product"
        # Exercise Odoo's PO references and code filters, not just PO syntax.
        with patch.dict(code_translations.python_translations, clear=True):
            translations = code_translations.get_python_translations("purchase_cost_recompute", "ru_RU")
            self.assertIn(source, translations)
            self.assertNotEqual(translations[source], source)
            translated = get_translation("purchase_cost_recompute", "ru_RU", source, {"product": product})
            self.assertIn(product, translated)
            self.assertNotIn("%(product)s", translated)
            self.assertNotEqual(translated, source % {"product": product})
            notification = (
                "Purchase lines: %(purchase_lines)s; receipts: %(receipts)s; "
                "issues: %(issues)s; returns: %(returns)s; "
                "inventory gains: %(inventory_gains)s; inventory losses: %(inventory_losses)s; "
                "scrap issues: %(scrap_issues)s; "
                "POS lines: %(pos_lines)s. Purchase total difference: %(difference)s."
            )
            self.assertIn(notification, translations)
            self.assertNotEqual(translations[notification], notification)


@tagged("post_install", "-at_install")
class TestPurchaseCostRecompute(PurchaseCostRecomputeCommon):
    def _amounts(self, orders):
        moves = self.env["stock.move"].search([
            ("product_id", "in", orders.order_line.product_id.ids),
            ("company_id", "in", orders.company_id.ids),
        ], order="id")
        return (
            orders.order_line.read(["price_unit", "discount", "product_qty", "tax_ids"]),
            moves.read(["value", "quantity", "date", "state"]),
            orders.order_line.product_id.read(["standard_price", "qty_available"]),
        )

    def _assert_rejected(self, orders, error=UserError):
        before = self._amounts(orders)
        with self.assertRaises(error):
            orders._apply_purchase_cost_recompute()
        self.assertEqual(self._amounts(orders), before)

    def test_action_is_temporary_and_open_cancel_do_not_change_business_values(self):
        order = self._purchase()
        before = self._amounts(order)
        action = order.action_open_cost_recompute()
        self.assertEqual(action["res_model"], "purchase.cost.recompute.wizard")
        self.assertEqual(action["target"], "new")
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertTrue(wizard._transient)
        self.assertEqual(wizard.order_ids, order)
        self.assertNotIn("reason", wizard._fields)
        self.assertEqual(self._amounts(order), before)
        wizard.unlink()
        self.assertEqual(self._amounts(order), before)

    def test_round_two_decimals_report_and_no_permanent_journal(self):
        order = self._purchase(price=27.33)
        receipt = order.order_line.move_ids
        original_total = order.amount_total
        original_facts = receipt.read(["quantity", "date", "state", "move_line_ids"])
        supplierinfo = self.env["product.supplierinfo"].search([
            ("product_tmpl_id", "=", self.product.product_tmpl_id.id),
        ])
        suppliers_before = supplierinfo.read(["price", "discount"])
        journals_before = self.env["pos.cost.recompute"].search_count([])
        manual_values_before = self.env["product.value"].search_count([])
        accounts_before = self.env["account.move"].search_count([])
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 32.80)
        self.assertFalse(order.order_line.tax_ids)
        self.assertAlmostEqual(receipt.value, 65.60)
        self.assertAlmostEqual(self.product.total_value, 65.60)
        self.assertAlmostEqual(self.product.standard_price, 32.80)
        self.assertEqual(result["purchase_lines"], 1)
        self.assertEqual(result["receipts"], 1)
        self.assertEqual(result["issues"], 0)
        self.assertEqual(result["returns"], 0)
        self.assertEqual(result["pos_lines"], 0)
        self.assertAlmostEqual(result["total_difference"], order.amount_total - original_total)
        self.assertAlmostEqual(result["total_difference"], 0.01)
        self.assertEqual(self.env["decimal.precision"].precision_get("Product Price"), 2)
        self.assertEqual(receipt.read(["quantity", "date", "state", "move_line_ids"]), original_facts)
        self.assertEqual(supplierinfo.read(["price", "discount"]), suppliers_before)
        self.assertEqual(self.env["pos.cost.recompute"].search_count([]), journals_before)
        self.assertEqual(self.env["product.value"].search_count([]), manual_values_before)
        self.assertEqual(self.env["account.move"].search_count([]), accounts_before)

    def test_half_cent_rounds_up(self):
        tax = self.tax.copy({"name": "Half cent", "amount": 50})
        order = self._purchase(price=0.03, taxes=tax)
        order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 0.05)
        self.assertEqual(order.order_line.move_ids.value, 0.10)

    def test_discount_is_preserved(self):
        order = self._purchase(discount=10)
        old_total = order.amount_total
        order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 120)
        self.assertEqual(order.order_line.discount, 10)
        self.assertEqual(order.order_line.price_subtotal, 216)
        self.assertEqual(order.amount_total, old_total)
        self.assertEqual(order.order_line.move_ids.value, 216)

    def test_multiple_percentage_taxes_follow_tax_base_order(self):
        self.tax.write({"sequence": 10, "include_base_amount": True})
        second = self.tax.copy({
            "name": "Second 5%", "amount": 5, "sequence": 20, "include_base_amount": False,
        })
        order = self._purchase(taxes=self.tax | second)
        order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 126)
        self.assertEqual(order.order_line.move_ids.value, 252)
        self.assertFalse(order.order_line.tax_ids)

    def test_zero_and_absent_taxes_are_noop_and_retry_is_idempotent(self):
        tax_zero = self.tax.copy({"name": "Zero", "amount": 0})
        zero = self._purchase(taxes=tax_zero)
        absent = self._purchase(taxes=self.env["account.tax"], date="2026-01-02 10:00:00")
        orders = zero | absent
        before = self._amounts(orders)
        result = orders._apply_purchase_cost_recompute()
        self.assertEqual(self._amounts(orders), before)
        self.assertEqual(result["purchase_lines"], 0)
        self.assertEqual(result["receipts"], 0)
        corrected = self._purchase(date="2026-01-03 10:00:00")
        mixed = orders | corrected
        result = mixed._apply_purchase_cost_recompute()
        self.assertEqual(result["purchase_lines"], 1)
        self.assertEqual(zero.order_line.tax_ids, tax_zero)
        before = self._amounts(mixed)
        result = mixed._apply_purchase_cost_recompute()
        self.assertEqual(result["purchase_lines"], 0)
        self.assertEqual(self._amounts(mixed), before)

    def test_numerically_unchanged_price_still_recomputes_history(self):
        order = self._purchase(price=0.01)
        issue = self._move(1, "2026-01-02 10:00:00")
        issue.value = 3
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 0.01)
        self.assertFalse(order.order_line.tax_ids)
        self.assertEqual(issue.value, 0.01)
        self.assertEqual(result["issues"], 1)

    def test_unsupported_taxes_and_precision_are_atomic(self):
        order = self._purchase()
        settings = [
            {"amount_type": "fixed"}, {"amount_type": "division"},
            {"amount": -20}, {"price_include_override": "tax_included"},
        ]
        for values in settings:
            with self.subTest(values=values), self.env.cr.savepoint() as savepoint:
                self.tax.write(values)
                self._assert_rejected(order)
                savepoint.rollback()
        precision = self.env["decimal.precision"].search([("name", "=", "Product Price")])
        precision.digits = 4
        self._assert_rejected(order)
        self.assertEqual(precision.digits, 4)

    def test_reverse_charge_percentage_tax_is_rejected(self):
        repartition = [
            Command.create({"repartition_type": "base"}),
            Command.create({
                "repartition_type": "tax", "factor_percent": 100,
                "account_id": self.company_data["default_account_tax_purchase"].id,
            }),
            Command.create({
                "repartition_type": "tax", "factor_percent": -100,
                "account_id": self.company_data["default_account_tax_purchase"].id,
            }),
        ]
        tax = self.tax.copy({
            "name": "Reverse charge", "invoice_repartition_line_ids": repartition,
            "refund_repartition_line_ids": repartition,
        })
        order = self._purchase(taxes=tax)
        self.assertTrue(tax.has_negative_factor)
        self._assert_rejected(order)

    def test_selected_and_unselected_receipts_share_fifo_without_repricing_other_purchases(self):
        first = self._purchase(quantity=2)
        second = self._purchase(price=200, quantity=3, date="2026-01-02 10:00:00")
        other = self._purchase(price=900, quantity=2, taxes=self.env["account.tax"],
                               date="2026-01-03 10:00:00")
        issue = self._move(4, "2026-01-04 10:00:00")
        later = self._move(2, "2026-01-05 10:00:00")
        source_values = other.order_line.read(["price_unit", "tax_ids"])
        result = (first | second)._apply_purchase_cost_recompute()
        self.assertEqual(issue.value, 2 * 120 + 2 * 240)
        self.assertEqual(later.value, 240 + 900)
        self.assertEqual(other.order_line.read(["price_unit", "tax_ids"]), source_values)
        self.assertEqual(other.order_line.move_ids.value, 1800)
        self.assertEqual(self.product.qty_available, 1)
        self.assertEqual(self.product.total_value, 900)
        self.assertEqual(result["receipts"], 2)
        self.assertEqual(result["issues"], 2)

    def test_negative_sale_return_sale_chain_preserves_physical_facts(self):
        order = self._purchase()
        first = self._move(150, "2026-01-02 10:00:00")
        returned = self._move(150, "2026-01-03 10:00:00", origin=first)
        later = self._move(1, "2026-01-04 10:00:00")
        moves = order.order_line.move_ids | first | returned | later
        before = moves.read(["quantity", "date", "state", "origin_returned_move_id"])
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(first.value, 18000)
        self.assertEqual(returned.value, 18000)
        self.assertEqual(later.value, 120)
        self.assertEqual(self.product.qty_available, 1)
        self.assertEqual(self.product.total_value, 120)
        self.assertEqual(self.product.standard_price, 120)
        self.assertEqual(moves.read(["quantity", "date", "state", "origin_returned_move_id"]), before)
        self.assertEqual(result["issues"], 2)
        self.assertEqual(result["returns"], 1)

    def test_partial_return_uses_corrected_origin_unit_value(self):
        order = self._purchase(price=25, quantity=3)
        issue = self._move(3, "2026-01-02 10:00:00")
        returned = self._move(1, "2026-01-03 10:00:00", origin=issue)
        order._apply_purchase_cost_recompute()
        self.assertEqual(issue.value, 90)
        self.assertEqual(returned.value, 30)
        self.assertEqual(self.product.total_value, 30)

    def test_earlier_origin_and_pos_cost_are_not_rewritten(self):
        self._purchase(price=90, quantity=2, taxes=self.env["account.tax"])
        sale = self._pos_order(quantity=2, date="2026-01-02 10:00:00")
        original = sale.picking_ids.move_ids
        corrected = self._purchase(price=100, quantity=2, date="2026-01-03 10:00:00")
        refund = self._pos_order(quantity=-1, date="2026-01-04 10:00:00", refund_line=sale.lines)
        before = (original.value, sale.lines.total_cost)
        result = corrected._apply_purchase_cost_recompute()
        self.assertEqual(before, (180, 180))
        self.assertEqual((original.value, sale.lines.total_cost), before)
        self.assertEqual(refund.picking_ids.move_ids.value, 90)
        self.assertEqual(refund.lines.total_cost, -90)
        self.assertEqual(result["pos_lines"], 1)
        self.assertEqual(self.product.total_value, 330)

    def test_empty_historical_stack_uses_prior_incoming_not_future_or_current_cost(self):
        order = self._purchase(quantity=1)
        exhausted = self._move(1, "2026-01-02 10:00:00")
        shortage = self._move(3, "2026-01-03 10:00:00")
        returned = self._move(3, "2026-01-04 10:00:00", origin=shortage)
        future = self._purchase(price=900, quantity=1, taxes=self.env["account.tax"],
                                date="2026-01-05 10:00:00")
        self.product.standard_price = 777
        order._apply_purchase_cost_recompute()
        self.assertEqual(exhausted.value, 120)
        self.assertEqual(shortage.value, 360)
        self.assertEqual(returned.value, 360)
        self.assertEqual(future.order_line.move_ids.value, 900)
        self.assertEqual(self.product.qty_available, 1)
        self.assertEqual(self.product.total_value, 900)

    def test_fifo_characterization_partial_shortage_and_empty_fallback(self):
        self._purchase(quantity=2)
        issue = self._move(3, "2026-01-02 10:00:00")
        returned = self._move(1, "2026-01-03 10:00:00", origin=issue)
        self.product.standard_price = 777
        historical = self.product.with_context(fifo_qty_already_processed=-3)
        self.assertEqual(historical._run_fifo(3, at_date=issue.date), 300)
        self.assertEqual(self.product._run_fifo(1, at_date=returned.date), 777)
        self.assertEqual(returned.value, 100)

    def test_missing_prior_source_is_rejected_even_with_later_purchase(self):
        self._move(1, "2026-01-01 10:00:00")
        order = self._purchase(quantity=2, date="2026-01-02 10:00:00")
        self._assert_rejected(order)

    def test_simultaneous_issues_consume_fifo_once_in_record_order(self):
        order = self._purchase(quantity=1)
        self._purchase(price=200, quantity=1, taxes=self.env["account.tax"],
                       date="2026-01-02 10:00:00")
        first = self._move(1, "2026-01-03 10:00:00")
        second = self._move(1, "2026-01-03 10:00:00")
        order._apply_purchase_cost_recompute()
        self.assertEqual(first.value, 120)
        self.assertEqual(second.value, 200)
        self.assertEqual(self.product.qty_available, 0)
        self.assertEqual(self.product.total_value, 0)

    def test_simultaneous_incoming_and_outgoing_are_rejected(self):
        order = self._purchase()
        self._move(1, "2026-01-01 10:00:00")
        self._assert_rejected(order)

    def test_invalid_customer_return_is_rejected_atomically(self):
        order = self._purchase()
        issue = self._move(2, "2026-01-02 10:00:00")
        returned = self._move(1, "2026-01-03 10:00:00", origin=issue)
        with self.env.cr.savepoint() as savepoint:
            returned.origin_returned_move_id = False
            self._assert_rejected(order)
            savepoint.rollback()
        with self.env.cr.savepoint() as savepoint:
            returned.date = fields.Datetime.to_datetime("2026-01-01 11:00:00")
            self._assert_rejected(order)
            savepoint.rollback()
        self._move(2, "2026-01-04 10:00:00", origin=issue)
        self._assert_rejected(order)

    def test_direct_sales_and_refunds_recompute_in_open_session(self):
        order = self._purchase()
        sale = self._pos_order(quantity=150, date="2026-01-02 10:00:00")
        refund = self._pos_order(quantity=-150, date="2026-01-03 10:00:00", refund_line=sale.lines)
        later = self._pos_order(quantity=1, date="2026-01-04 10:00:00")
        orders = sale | refund | later
        business_fields = ["amount_total", "amount_paid", "amount_tax", "state", "date_order", "payment_ids"]
        before = orders.read(business_fields)
        payments = orders.payment_ids.read(["amount", "payment_date", "payment_method_id"])
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 18000)
        self.assertEqual(refund.lines.total_cost, -18000)
        self.assertEqual(later.lines.total_cost, 120)
        self.assertEqual(sale.margin, 12000)
        self.assertEqual(refund.margin, -12000)
        self.assertEqual(later.margin, 80)
        self.assertEqual(result["pos_lines"], 3)
        self.assertEqual(self.pos_session.state, "opened")
        self.assertEqual(orders.read(business_fields), before)
        self.assertEqual(orders.payment_ids.read(["amount", "payment_date", "payment_method_id"]), payments)

    def test_closed_shared_source_recomputes_all_lines_preserving_revenue(self):
        order = self._purchase(quantity=5)
        self.company.point_of_sale_update_stock_quantities = "closing"
        first = self._pos_order(quantity=1)
        second = self._pos_order(quantity=3, date="2026-01-02 11:00:00")
        self._close_pos_session()
        self.assertFalse((first | second).picking_ids)
        account = self.pos_session.move_id
        self.assertTrue(account)
        account_before = account.line_ids.read(["balance", "debit", "credit", "account_id"])
        states = (first | second).mapped("state")
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(first.lines.total_cost, 120)
        self.assertEqual(second.lines.total_cost, 360)
        self.assertEqual(first.margin, 80)
        self.assertEqual(second.margin, 240)
        self.assertEqual(result["pos_lines"], 2)
        self.assertEqual(self.pos_session.state, "closed")
        self.assertEqual((first | second).mapped("state"), states)
        self.assertEqual(account.line_ids.read(["balance", "debit", "credit", "account_id"]), account_before)

    def test_unfinished_direct_source_is_rejected(self):
        order = self._purchase()
        sale = self._pos_order()
        with self.env.cr.savepoint() as savepoint:
            sale.picking_ids.move_ids.state = "assigned"
            self._assert_rejected(order)
            savepoint.rollback()
    def test_open_shared_session_source_is_rejected(self):
        order = self._purchase()
        self.company.point_of_sale_update_stock_quantities = "closing"
        self._pos_order()
        self._assert_rejected(order)

    def test_late_pos_failure_rolls_back_then_retry_succeeds(self):
        order = self._purchase()
        sale = self._pos_order()
        before = self._amounts(order)
        cost_before = sale.lines.total_cost
        original = type(sale.lines)._compute_total_cost

        def fail_after_cost_update(lines, moves):
            original(lines, moves)
            self.assertEqual(order.order_line.price_unit, 120)
            self.assertEqual(sale.picking_ids.move_ids.value, 120)
            raise UserError("Failure after POS cost update")

        with patch.object(type(sale.lines), "_compute_total_cost", fail_after_cost_update):
            with self.assertRaisesRegex(UserError, "Failure after POS cost update"):
                order._apply_purchase_cost_recompute()
        self.assertEqual(self._amounts(order), before)
        self.assertEqual(sale.lines.total_cost, cost_before)
        order._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 120)

    def test_invalid_purchase_selection(self):
        with self.assertRaises(UserError):
            self.env["purchase.order"]._apply_purchase_cost_recompute()
        order = self._purchase()
        for values in ({"locked": True}, {"state": "draft"}, {"state": "cancel"},
                       {"currency_id": self.other_currency.id}):
            with self.subTest(values=values), self.env.cr.savepoint() as savepoint:
                order.write(values)
                self._assert_rejected(order)
                savepoint.rollback()
        for values in ({"price_unit": 0}, {"price_unit": -1}, {"discount": 100},
                       {"discount": -1}):
            with self.subTest(values=values), self.env.cr.savepoint() as savepoint:
                order.order_line.write(values)
                self._assert_rejected(order)
                savepoint.rollback()
        incomplete = self._purchase(date="2026-01-02 10:00:00", receive=False)
        self._assert_rejected(order | incomplete)

    def test_unsupported_product_and_stock_configuration(self):
        order = self._purchase()
        variants = [
            (self.product, {"tracking": "lot"}),
            (self.category, {"property_cost_method": "average"}),
            (self.company, {"inventory_valuation": "real_time"}),
        ]
        for record, values in variants:
            with self.subTest(values=values), self.env.cr.savepoint() as savepoint:
                record.write(values)
                self._assert_rejected(order)
                savepoint.rollback()
        move = order.order_line.move_ids
        with self.env.cr.savepoint() as savepoint:
            move.move_line_ids.owner_id = self.vendor
            self._assert_rejected(order)
            savepoint.rollback()
        internal = self.env["stock.move"].create({
            "product_id": self.product.id, "product_uom": self.product.uom_id.id,
            "product_uom_qty": 1, "location_id": self.stock_location.id,
            "location_dest_id": self.stock_location_components.id,
        })
        internal._action_confirm(merge=False)
        self._assert_rejected(order)

    def test_draft_and_posted_supplier_bills_block_correction(self):
        order = self._purchase()
        bill = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.vendor.id,
            "invoice_date": "2026-01-02",
            "invoice_line_ids": [Command.create({
                "product_id": self.product.id, "quantity": 2, "price_unit": 100,
                "purchase_line_id": order.order_line.id,
                "tax_ids": [Command.set(self.tax.ids)],
            })],
        })
        self._assert_rejected(order)
        bill.action_post()
        self._assert_rejected(order)

    def test_non_base_unit_and_supplier_return_are_rejected(self):
        order = self._purchase()
        with self.env.cr.savepoint() as savepoint:
            order.order_line.product_uom_id = self.env.ref("uom.product_uom_dozen")
            self._assert_rejected(order)
            savepoint.rollback()
        with freeze_time("2026-01-02 10:00:00"):
            returned = self.env["stock.move"].create({
                "product_id": self.product.id, "product_uom": self.product.uom_id.id,
                "product_uom_qty": 1, "location_id": self.stock_location.id,
                "location_dest_id": self.supplier_location.id,
                "origin_returned_move_id": order.order_line.move_ids.id,
            })
            returned._action_confirm(merge=False)
            returned.quantity = 1
            returned.picked = True
            returned._action_done()
        self._assert_rejected(order)

    def test_manual_value_and_locked_period_block_correction(self):
        order = self._purchase()
        with self.env.cr.savepoint() as savepoint:
            order.order_line.move_ids.value_manual = 201
            self._assert_rejected(order)
            savepoint.rollback()
        self.company.purchase_lock_date = "2026-01-02"
        self._assert_rejected(order)

    def test_stock_accounting_dependency_blocks_correction(self):
        order = self._purchase()
        account = self.env["account.move"].create({
            "journal_id": self.company_data["default_journal_misc"].id,
            "date": "2026-01-01",
        })
        order.order_line.move_ids.account_move_id = account
        self._assert_rejected(order)

    def test_existing_protected_stock_repair_is_preserved(self):
        order = self._purchase()
        sale = self._pos_order()
        self._close_pos_session()
        move = sale.picking_ids.move_ids
        move.value = 0
        operation = self.env["pos.cost.recompute"].create({
            "selection_type": "orders", "order_ids": [Command.set(sale.ids)],
            "cost_mode": "all", "reason": "Protect existing stock repair",
            "repair_stock_values": True,
        })
        operation.action_preview()
        self.assertEqual(operation.stock_repair_count, 1, operation.stock_line_ids.mapped("skip_reason"))
        operation.acknowledge_stock_repair = True
        operation.action_apply()
        self.assertTrue(move.cost_repair_line_id)
        evidence = operation.stock_line_ids.read(["move_id", "new_value", "actual_value"])
        self._assert_rejected(order)
        self.assertEqual(operation.state, "done")
        self.assertEqual(operation.stock_line_ids.read(["move_id", "new_value", "actual_value"]), evidence)

    def test_mixed_closed_session_source_is_rejected(self):
        order = self._purchase(quantity=5)
        self.company.point_of_sale_update_stock_quantities = "closing"
        sale = self._pos_order(quantity=2)
        self._pos_order(quantity=-1, date="2026-01-02 11:00:00", refund_line=sale.lines)
        self._close_pos_session()
        self._assert_rejected(order)

    def test_draft_pos_correction_does_not_block_purchase_recompute(self):
        if "pos.order.correction" not in self.env:
            self.skipTest("The optional POS correction module is not installed.")
        order = self._purchase()
        sale = self._pos_order()
        self._close_pos_session()
        self.env.user.group_ids |= self.env.ref("pos_order_correction.group_pos_order_correction")
        with freeze_time("2026-01-04 10:00:00"):
            self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        correction = self.env["pos.order.correction"].browse(
            sale.action_prepare_correction()["res_id"]
        )
        snapshot = correction.source_snapshot
        action = order.action_open_cost_recompute()
        result = self.env["purchase.cost.recompute.wizard"].browse(action["res_id"]).action_apply()
        self.assertEqual(result["params"]["type"], "success")
        self.assertEqual(correction.state, "draft")
        self.assertEqual(correction.source_snapshot, snapshot)
        self.assertFalse(correction.applied_order_id)

    def test_applied_pos_correction_blocks_purchase_recompute(self):
        if "pos.order.correction" not in self.env:
            self.skipTest("The optional POS correction module is not installed.")
        order = self._purchase()
        sale = self._pos_order()
        self._close_pos_session()
        self.env.user.group_ids |= self.env.ref("pos_order_correction.group_pos_order_correction")
        with freeze_time("2026-01-04 10:00:00"):
            self._start_pos_session(self.cash_pm1 | self.bank_pm1, 0)
        correction = self.env["pos.order.correction"].browse(
            sale.action_prepare_correction()["res_id"]
        )
        correction.line_ids.price_unit += 1
        correction.payment_ids.amount += 1
        correction.reason = "Correct the sale price"
        correction.action_apply()
        self._assert_rejected(order)

    def test_shared_product_cost_is_isolated_for_positive_zero_and_negative_stock(self):
        other = self.env["res.company"].create({
            "name": "Purchase cost other company", "currency_id": self.company.currency_id.id,
            "inventory_valuation": "periodic",
        })
        self.env.user.company_ids |= other
        self.category.with_company(other).property_cost_method = "fifo"
        self.product.company_id = False
        for issued in (1, 2, 3):
            with self.subTest(issued=issued), self.env.cr.savepoint() as savepoint:
                order = self._purchase()
                issue = self._move(issued, "2026-01-02 10:00:00")
                foreign = self._purchase(
                    price=900, quantity=5, taxes=self.env["account.tax"],
                    date="2026-01-03 10:00:00", company=other,
                )
                foreign_product = self.product.with_company(other).with_context(allowed_company_ids=other.ids)
                before_foreign = (foreign_product.standard_price, foreign_product.qty_available,
                                  foreign.order_line.move_ids.value)
                order.with_context(allowed_company_ids=(self.company | other).ids)._apply_purchase_cost_recompute()
                own_product = self.product.with_company(self.company).with_context(allowed_company_ids=self.company.ids)
                self.assertEqual(own_product.standard_price, 120)
                self.assertEqual(own_product.qty_available, 2 - issued)
                self.assertEqual(issue.value, issued * 120)
                self.assertEqual(
                    (foreign_product.standard_price, foreign_product.qty_available,
                     foreign.order_line.move_ids.value), before_foreign,
                )
                savepoint.rollback()

    def test_mixed_and_unauthorized_companies_are_rejected(self):
        other = self.env["res.company"].create({
            "name": "Purchase cost inaccessible company", "currency_id": self.company.currency_id.id,
        })
        self.product.company_id = False
        self.env.user.company_ids |= other
        self.category.with_company(other).property_cost_method = "fifo"
        own = self._purchase()
        foreign = self._purchase(
            price=900, quantity=5, taxes=self.env["account.tax"],
            date="2026-01-03 10:00:00", company=other,
        )
        selection = (own | foreign).with_context(allowed_company_ids=(self.company | other).ids)
        self._assert_rejected(selection)
        user = new_test_user(
            self.env, login="purchase-cost-one-company",
            groups="purchase.group_purchase_manager,stock.group_stock_manager",
            company_id=self.company.id,
        )
        with self.assertRaises(AccessError):
            foreign.with_user(user).with_context(allowed_company_ids=self.company.ids)._apply_purchase_cost_recompute()

    def test_direct_access_requires_both_manager_groups(self):
        order = self._purchase()
        before = self._amounts(order)
        for index, group in enumerate(("purchase.group_purchase_manager", "stock.group_stock_manager")):
            user = new_test_user(
                self.env, login=f"purchase-cost-one-manager-{index}",
                groups=group, company_id=self.company.id,
            )
            for method in ("action_open_cost_recompute", "_apply_purchase_cost_recompute"):
                with self.subTest(group=group, method=method), self.assertRaises(AccessError):
                    getattr(order.with_user(user), method)()
        self.assertEqual(self._amounts(order), before)

    def test_missing_stock_visibility_and_write_access_are_rejected(self):
        order = self._purchase()
        user = new_test_user(
            self.env, login="purchase-cost-limited-manager",
            groups="purchase.group_purchase_manager,stock.group_stock_manager,"
                   "point_of_sale.group_pos_manager,product.group_product_manager",
            company_id=self.company.id,
        )
        before = self._amounts(order)
        model = self.env["ir.model"]._get("stock.move")
        for read in (True, False):
            with self.subTest(read=read), self.env.cr.savepoint() as savepoint:
                self.env["ir.rule"].create({
                    "name": "Exclude correction source", "model_id": model.id,
                    "domain_force": f"[('id', '!=', {order.order_line.move_ids.id})]",
                    "perm_read": read, "perm_write": not read,
                    "perm_create": False, "perm_unlink": False,
                })
                with self.assertRaises(AccessError):
                    order.with_user(user)._apply_purchase_cost_recompute()
                savepoint.rollback()
        self.assertEqual(self._amounts(order), before)

    def test_required_pos_access_is_not_elevated(self):
        order = self._purchase()
        sale = self._pos_order()
        user = new_test_user(
            self.env, login="purchase-cost-no-pos-rights",
            groups="purchase.group_purchase_manager,stock.group_stock_manager,product.group_product_manager",
            company_id=self.company.id,
        )
        before = self._amounts(order)
        old_cost = sale.lines.total_cost
        with self.assertRaises(AccessError):
            order.with_user(user)._apply_purchase_cost_recompute()
        self.assertEqual(self._amounts(order), before)
        self.assertEqual(sale.lines.total_cost, old_cost)

    def test_authorized_nonadministrator_can_correct_purchase_and_pos(self):
        order = self._purchase()
        sale = self._pos_order()
        user = new_test_user(
            self.env, login="purchase-cost-authorized-manager",
            groups="purchase.group_purchase_manager,stock.group_stock_manager,"
                   "point_of_sale.group_pos_manager,product.group_product_manager",
            company_id=self.company.id,
        )
        self.assertFalse(user.has_group("base.group_system"))
        result = order.with_user(user)._apply_purchase_cost_recompute()
        self.assertEqual(result["purchase_lines"], 1)
        self.assertEqual(sale.lines.total_cost, 120)

    def test_ordinary_price_change_does_not_trigger_historical_pos_recompute(self):
        order = self._purchase()
        sale = self._pos_order()
        old_issue = sale.picking_ids.move_ids.value
        old_cost = sale.lines.total_cost
        order.order_line.price_unit = 150
        self.assertEqual(order.order_line.move_ids.value, 300)
        self.assertEqual(sale.picking_ids.move_ids.value, old_issue)
        self.assertEqual(sale.lines.total_cost, old_cost)
        self.assertEqual(order.order_line.tax_ids, self.tax)
        operation = self.env["pos.cost.recompute"].create({
            "selection_type": "orders", "order_ids": [Command.set(sale.ids)],
            "cost_mode": "all", "reason": "Existing tool unchanged",
        })
        operation.action_preview()
        self.assertEqual(operation.skipped_count, 1)
        self.assertIn("not closed", operation.line_ids.skip_reason)
