from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged

from .common import PurchaseCostRecomputeCommon


@tagged("post_install", "-at_install")
class TestPurchaseCostRecomputeInventory(PurchaseCostRecomputeCommon):
    def _adjust(self, change, date, product=None):
        product = product or self.product
        with freeze_time(date):
            quant = self.env["stock.quant"]._gather(product, self.stock_location, strict=True)
            if quant:
                quant = quant[0]
                quant.inventory_quantity = quant.quantity + change
            else:
                quant = self.env["stock.quant"].create({
                    "product_id": product.id,
                    "location_id": self.stock_location.id,
                    "inventory_quantity": change,
                })
            quant.action_apply_inventory()
            return self.env["stock.move"].search([
                ("product_id", "=", product.id),
                ("is_inventory", "=", True),
                ("date", "=", fields.Datetime.now()),
            ], order="id desc", limit=1)

    def _scrap(self, quantity, date, product=None, picking=None):
        product = product or self.product
        with freeze_time(date):
            scrap = self.env["stock.scrap"].create({
                "company_id": self.env.company.id,
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "scrap_qty": quantity,
                "location_id": self.stock_location.id,
                "scrap_location_id": product.property_stock_inventory.id,
                "picking_id": picking.id if picking else False,
            })
            scrap.do_scrap()
            return scrap.move_ids

    def test_inventory_loss_consumes_purchase_fifo(self):
        selected = self._purchase(price=100, quantity=2)
        other = self._purchase(price=200, quantity=3, taxes=self.env["account.tax"],
                               date="2026-01-02 10:00:00")
        loss = self._adjust(-3, "2026-01-03 10:00:00")
        self.assertTrue(loss.is_inventory)
        self.assertFalse(loss.scrap_id)
        result = selected._apply_purchase_cost_recompute()
        self.assertEqual(loss.value, 440)
        self.assertEqual(other.order_line.move_ids.value, 600)
        self.assertEqual(self.product.qty_available, 2)
        self.assertEqual(self.product.total_value, 400)
        self.assertEqual(result["issues"], 1)
        self.assertEqual(result["inventory_losses"], 1)

    def test_scrap_revalued_without_reposting(self):
        order = self._purchase(price=725, quantity=1)
        scrap = self._scrap(1, "2026-01-02 10:00:00")
        before = scrap.read(["date", "quantity", "state", "location_id", "location_dest_id", "scrap_id"])
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.move_ids.value, 870)
        self.assertEqual(scrap.value, 870)
        self.assertEqual(scrap.read(["date", "quantity", "state", "location_id", "location_dest_id", "scrap_id"]), before)
        self.assertEqual(self.product.qty_available, 0)
        self.assertEqual(result["scrap_issues"], 1)
        self.assertEqual(result["issues"], 1)

    def test_gain_uses_corrected_full_pre_gain_remainder(self):
        selected = self._purchase(price=100, quantity=5)
        other = self._purchase(price=200, quantity=5, taxes=self.env["account.tax"],
                               date="2026-01-02 10:00:00")
        gain = self._adjust(2, "2026-01-03 10:00:00")
        self.product.standard_price = 777
        before = gain.read(["date", "quantity", "state", "location_id", "location_dest_id"])
        result = selected._apply_purchase_cost_recompute()
        self.assertEqual(gain.value, 320)
        self.assertEqual(other.order_line.move_ids.value, 1000)
        self.assertEqual(self.product.qty_available, 12)
        self.assertEqual(self.product.total_value, 1920)
        self.assertEqual(gain.read(["date", "quantity", "state", "location_id", "location_dest_id"]), before)
        self.assertEqual(result["inventory_gains"], 1)
        self.assertEqual(result["receipts"], 1)

    def test_gain_after_empty_stock_uses_last_proven_receipt(self):
        order = self._purchase(price=100, quantity=1)
        self._move(1, "2026-01-02 10:00:00")
        gain = self._adjust(2, "2026-01-03 10:00:00")
        self.product.standard_price = 777
        order._apply_purchase_cost_recompute()
        self.assertEqual(gain.value, 240)
        self.assertEqual(self.product.total_value, 240)

    def test_gain_after_shortage_uses_prior_incoming_value(self):
        order = self._purchase(price=100, quantity=1)
        self._move(4, "2026-01-02 10:00:00")
        gain = self._adjust(5, "2026-01-03 10:00:00")
        order._apply_purchase_cost_recompute()
        self.assertEqual(gain.value, 600)
        self.assertEqual(self.product.qty_available, 2)
        self.assertEqual(self.product.total_value, 240)

    def test_gain_without_historical_incoming_basis_refuses_without_card_fallback(self):
        order = self._purchase(price=100, quantity=1)
        self._move(1, "2026-01-02 10:00:00")
        gain = self._adjust(1, "2026-01-03 10:00:00")
        self.product.standard_price = 777
        before = (order.order_line.price_unit, order.order_line.tax_ids.ids, gain.value)
        with patch.object(type(self.product), "_get_last_in",
                          return_value=self.env["stock.move"]):
            with self.assertRaisesRegex(UserError, "No earlier incoming value proves the inventory gain cost"):
                order._apply_purchase_cost_recompute()
        self.assertEqual((order.order_line.price_unit, order.order_line.tax_ids.ids, gain.value), before)

    def test_gain_and_loss_chain_recomputed_once(self):
        order = self._purchase(price=100, quantity=2)
        first = self._adjust(1, "2026-01-02 10:00:00")
        loss = self._adjust(-2, "2026-01-03 10:00:00")
        last = self._adjust(1, "2026-01-04 10:00:00")
        result = order._apply_purchase_cost_recompute()
        self.assertEqual([first.value, loss.value, last.value], [120, 240, 120])
        self.assertEqual(self.product.total_value, 240)
        self.assertEqual((result["inventory_gains"], result["inventory_losses"]), (2, 1))

    def test_gain_after_corrected_customer_return(self):
        order = self._purchase(price=100, quantity=1)
        issue = self._move(2, "2026-01-02 10:00:00")
        returned = self._move(2, "2026-01-03 10:00:00", origin=issue)
        gain = self._adjust(1, "2026-01-04 10:00:00")
        order._apply_purchase_cost_recompute()
        self.assertEqual(returned.value, 240)
        self.assertEqual(gain.value, 120)
        self.assertEqual(self.product.total_value, 240)

    def test_gain_feeds_later_pos_sale_and_refund_without_changing_revenue(self):
        order = self._purchase(price=100, quantity=1)
        self._move(1, "2026-01-02 10:00:00")
        gain = self._adjust(1, "2026-01-03 10:00:00")
        sale = self._pos_order(date="2026-01-04 10:00:00")
        refund = self._pos_order(quantity=-1, date="2026-01-05 10:00:00",
                                 refund_line=sale.lines)
        orders = sale | refund
        before = orders.read(["amount_total", "amount_paid", "state", "payment_ids"])
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(gain.value, 120)
        self.assertEqual(sale.lines.total_cost, 120)
        self.assertEqual(refund.lines.total_cost, -120)
        self.assertEqual(result["pos_lines"], 2)
        self.assertEqual(orders.read(["amount_total", "amount_paid", "state", "payment_ids"]), before)

    def test_gain_ignores_future_receipt_and_current_product_cost(self):
        order = self._purchase(price=100, quantity=2)
        gain = self._adjust(1, "2026-01-02 10:00:00")
        later = self._purchase(price=900, quantity=1, taxes=self.env["account.tax"],
                               date="2026-01-03 10:00:00")
        later_value = later.order_line.move_ids.value
        self.product.standard_price = 777
        order._apply_purchase_cost_recompute()
        self.assertEqual(gain.value, 120)
        self.assertEqual(later.order_line.move_ids.value, later_value)

    def test_gain_keeps_fractional_historical_average(self):
        order = self._purchase(price=1.11, quantity=3)
        self._purchase(price=2, quantity=3, taxes=self.env["account.tax"],
                       date="2026-01-02 10:00:00")
        gain = self._adjust(3, "2026-01-03 10:00:00")
        order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 1.33)
        # 9.99 / 6 * 3 = 4.995; rounding the intermediate unit cost to
        # 1.67 would incorrectly produce 5.01 instead of the monetary 5.00.
        self.assertEqual(gain.value, 5.00)
        self.assertEqual(self.product.total_value, 14.99)

    def test_same_timestamp_loss_and_sale_consume_fifo_once(self):
        order = self._purchase(price=100, quantity=1)
        self._purchase(price=200, quantity=2, taxes=self.env["account.tax"],
                       date="2026-01-02 10:00:00")
        loss = self._adjust(-1, "2026-01-03 10:00:00")
        sale = self._move(1, "2026-01-03 10:00:00")
        order._apply_purchase_cost_recompute()
        self.assertEqual((loss.value, sale.value), (120, 200))
        self.assertEqual(self.product.total_value, 200)

    def test_inventory_gain_with_manual_value_is_refused_atomically(self):
        order = self._purchase(price=100, quantity=2)
        gain = self._adjust(1, "2026-01-02 10:00:00")
        gain.value_manual = 222
        before = (order.order_line.price_unit, order.order_line.tax_ids.ids, gain.value)
        with self.assertRaises(UserError):
            order._apply_purchase_cost_recompute()
        self.assertEqual((order.order_line.price_unit, order.order_line.tax_ids.ids, gain.value), before)

    def test_inventory_loss_and_scrap_manual_values_are_refused_atomically(self):
        for source in ("loss", "scrap"):
            with self.subTest(source=source), self.env.cr.savepoint() as sp:
                order = self._purchase(price=100, quantity=2)
                move = (self._adjust(-1, "2026-01-02 10:00:00") if source == "loss"
                        else self._scrap(1, "2026-01-02 10:00:00"))
                move.value_manual = 222
                before = (order.order_line.price_unit, order.order_line.tax_ids.ids, move.value)
                with self.assertRaises(UserError):
                    order._apply_purchase_cost_recompute()
                self.assertEqual((order.order_line.price_unit, order.order_line.tax_ids.ids,
                                  move.value), before)
                sp.rollback()

    def test_adjustment_source_visibility_is_required(self):
        order = self._purchase(price=100, quantity=2)
        scrap = self._scrap(1, "2026-01-02 10:00:00")
        user = new_test_user(
            self.env, login="purchase-adjustment-limited-manager",
            groups="purchase.group_purchase_manager,stock.group_stock_manager,"
                   "point_of_sale.group_pos_manager,product.group_product_manager",
            company_id=self.company.id,
        )
        self.env["ir.rule"].create({
            "name": "Exclude adjustment source",
            "model_id": self.env["ir.model"]._get("stock.scrap").id,
            "domain_force": f"[('id', '!=', {scrap.scrap_id.id})]",
            "perm_read": True,
            "perm_write": False,
            "perm_create": False,
            "perm_unlink": False,
        })
        with self.assertRaises(AccessError):
            order.with_user(user)._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 100)

    def test_late_failure_after_gain_rolls_back_and_retry_succeeds(self):
        order = self._purchase(price=100, quantity=2)
        gain = self._adjust(1, "2026-01-02 10:00:00")
        sale = self._pos_order(date="2026-01-03 10:00:00")
        before = (order.order_line.price_unit, order.order_line.tax_ids.ids,
                  order.order_line.move_ids.value, gain.value, sale.lines.total_cost)
        original = type(sale.lines)._compute_total_cost

        def fail_after_cost_update(lines, moves):
            original(lines, moves)
            self.assertEqual(gain.value, 120)
            raise UserError("Failure after inventory gain")

        with patch.object(type(sale.lines), "_compute_total_cost", fail_after_cost_update):
            with self.assertRaisesRegex(UserError, "Failure after inventory gain"):
                order._apply_purchase_cost_recompute()
        self.assertEqual((order.order_line.price_unit, order.order_line.tax_ids.ids,
                          order.order_line.move_ids.value, gain.value, sale.lines.total_cost), before)
        order._apply_purchase_cost_recompute()
        self.assertEqual(gain.value, 120)
        self.assertEqual(sale.lines.total_cost, 120)

    def test_gain_cost_ignores_other_company_receipt(self):
        other = self.env["res.company"].create({
            "name": "Inventory gain other company", "currency_id": self.company.currency_id.id,
            "inventory_valuation": "periodic",
        })
        self.env.user.company_ids |= other
        self.category.with_company(other).property_cost_method = "fifo"
        self.product.company_id = False
        order = self._purchase(price=100, quantity=2)
        foreign = self._purchase(price=900, quantity=5, taxes=self.env["account.tax"],
                                 date="2026-01-02 10:00:00", company=other)
        gain = self._adjust(1, "2026-01-03 10:00:00")
        before_foreign = foreign.order_line.move_ids.value
        order.with_context(allowed_company_ids=(self.company | other).ids)._apply_purchase_cost_recompute()
        self.assertEqual(gain.value, 120)
        self.assertEqual(foreign.order_line.move_ids.value, before_foreign)

    def test_empty_and_negative_gain_bases_ignore_other_company_receipt(self):
        other = self.env["res.company"].create({
            "name": "Inventory gain fallback other company", "currency_id": self.company.currency_id.id,
            "inventory_valuation": "periodic",
        })
        self.env.user.company_ids |= other
        self.category.with_company(other).property_cost_method = "fifo"
        self.product.company_id = False
        order = self._purchase(price=100, quantity=1)
        self._move(1, "2026-01-02 10:00:00")
        foreign = self._purchase(price=900, quantity=5, taxes=self.env["account.tax"],
                                 date="2026-01-02 12:00:00", company=other)
        first = self._adjust(1, "2026-01-03 10:00:00")
        self._move(2, "2026-01-04 10:00:00")
        second = self._adjust(2, "2026-01-05 10:00:00")
        foreign_value = foreign.order_line.move_ids.value
        order.with_context(allowed_company_ids=(self.company | other).ids)._apply_purchase_cost_recompute()
        self.assertEqual((first.value, second.value), (120, 240))
        self.assertEqual(foreign.order_line.move_ids.value, foreign_value)

    def test_unproven_inventory_loss_source_is_rejected(self):
        order = self._purchase(price=100, quantity=2)
        with freeze_time("2026-01-02 10:00:00"):
            move = self.env["stock.move"].create({
                "product_id": self.product.id,
                "product_uom": self.product.uom_id.id,
                "product_uom_qty": 1,
                "location_id": self.stock_location.id,
                "location_dest_id": self.product.property_stock_inventory.id,
            })
            move._action_confirm(merge=False)
            move.quantity = 1
            move.picked = True
            move._action_done()
        with self.assertRaises(UserError):
            order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 100)

    def test_inventory_flag_does_not_authorize_customer_issue(self):
        order = self._purchase(price=100, quantity=2)
        issue = self._move(1, "2026-01-02 10:00:00")
        issue.is_inventory = True
        with self.assertRaisesRegex(UserError, "Unsupported receipt"):
            order._apply_purchase_cost_recompute()
        self.assertEqual(order.order_line.price_unit, 100)

    def test_simultaneous_gains_share_earlier_cost(self):
        order = self._purchase(price=100, quantity=5)
        first = self._adjust(1, "2026-01-02 10:00:00")
        second = self._adjust(1, "2026-01-02 10:00:00")
        self.assertNotEqual(first, second)
        order._apply_purchase_cost_recompute()
        self.assertEqual((first.value, second.value), (120, 120))
        self.assertEqual(self.product.total_value, 840)

    def test_gain_and_receipt_same_timestamp_are_rejected(self):
        order = self._purchase(price=100, quantity=2)
        self._adjust(1, "2026-01-02 10:00:00")
        self._purchase(price=200, quantity=1, taxes=self.env["account.tax"],
                       date="2026-01-02 10:00:00")
        with self.assertRaises(UserError):
            order._apply_purchase_cost_recompute()

    def test_existing_pos_source_does_not_include_linked_scrap(self):
        order = self._purchase(price=100, quantity=2)
        sale = self._pos_order(date="2026-01-02 10:00:00")
        self.assertTrue(sale.picking_ids)
        scrap = self._scrap(1, "2026-01-03 10:00:00", picking=sale.picking_ids[0])
        result = order._apply_purchase_cost_recompute()
        self.assertEqual(scrap.value, 120)
        self.assertEqual(sale.lines.total_cost, 120)
        self.assertEqual(result["pos_lines"], 1)

    def test_counts_and_repeat_with_all_adjustment_types(self):
        order = self._purchase(price=100, quantity=12)
        gains = (self._adjust(1, "2026-01-02 10:00:00")
                 | self._adjust(1, "2026-01-03 10:00:00"))
        losses = (self._adjust(-1, "2026-01-04 10:00:00")
                  | self._adjust(-1, "2026-01-05 10:00:00")
                  | self._adjust(-1, "2026-01-06 10:00:00"))
        scrap = (self._scrap(1, "2026-01-07 10:00:00")
                 | self._scrap(1, "2026-01-08 10:00:00")
                 | self._scrap(1, "2026-01-09 10:00:00")
                 | self._scrap(1, "2026-01-10 10:00:00"))
        business_fields = ["date", "quantity", "state", "location_id", "location_dest_id",
                           "move_line_ids", "scrap_id"]
        before_facts = (gains | losses | scrap).read(business_fields)
        source_facts = scrap.scrap_id.read([
            "state", "scrap_qty", "product_id", "location_id", "scrap_location_id", "move_ids"
        ])
        journals_before = self.env["pos.cost.recompute"].search_count([])
        result = order._apply_purchase_cost_recompute()
        self.assertEqual((result["receipts"], result["inventory_gains"],
                          result["inventory_losses"], result["scrap_issues"], result["issues"]),
                         (1, 2, 3, 4, 7))
        self.assertEqual((gains | losses | scrap).mapped("value"), [120] * 9)
        self.assertEqual(self.product.qty_available, 7)
        self.assertEqual(self.product.total_value, 840)
        self.assertEqual(self.product.standard_price, 120)
        self.assertEqual((gains | losses | scrap).read(business_fields), before_facts)
        self.assertEqual(scrap.scrap_id.read([
            "state", "scrap_qty", "product_id", "location_id", "scrap_location_id", "move_ids"
        ]), source_facts)
        self.assertEqual(self.env["pos.cost.recompute"].search_count([]), journals_before)
        values = (order.order_line.price_unit, (gains | losses | scrap).mapped("value"))
        repeated = order._apply_purchase_cost_recompute()
        self.assertEqual((repeated["purchase_lines"], repeated["receipts"],
                          repeated["inventory_gains"], repeated["inventory_losses"],
                          repeated["scrap_issues"]), (0, 0, 0, 0, 0))
        self.assertEqual((order.order_line.price_unit,
                          (gains | losses | scrap).mapped("value")), values)

    def test_opening_and_cancelling_wizard_preserves_adjustments(self):
        order = self._purchase(price=100, quantity=2)
        gain = self._adjust(1, "2026-01-02 10:00:00")
        before = (order.order_line.price_unit, order.order_line.tax_ids.ids, gain.value)
        action = order.action_open_cost_recompute()
        wizard = self.env[action["res_model"]].browse(action["res_id"])
        self.assertEqual((order.order_line.price_unit, order.order_line.tax_ids.ids, gain.value), before)
        wizard.unlink()
        self.assertEqual((order.order_line.price_unit, order.order_line.tax_ids.ids, gain.value), before)

    def test_wizard_reports_adjustments_and_empty_repeat(self):
        order = self._purchase(price=100, quantity=2)
        self._adjust(1, "2026-01-02 10:00:00")
        self._adjust(-1, "2026-01-03 10:00:00")
        self._scrap(1, "2026-01-04 10:00:00")
        wizard = self.env["purchase.cost.recompute.wizard"].browse(
            order.action_open_cost_recompute()["res_id"]
        )
        result = wizard.action_apply()
        message = result["params"]["message"]
        for text in ("inventory gains: 1", "inventory losses: 1", "scrap issues: 1",
                     "issues: 2"):
            self.assertIn(text, message)
        retry = self.env["purchase.cost.recompute.wizard"].browse(
            order.action_open_cost_recompute()["res_id"]
        ).action_apply()
        self.assertEqual(retry["params"]["message"], "No purchase lines required correction.")

    def test_earlier_adjustment_is_left_unchanged(self):
        self._purchase(price=100, quantity=3, taxes=self.env["account.tax"],
                       date="2026-01-01 10:00:00")
        earlier = (self._adjust(1, "2026-01-02 10:00:00")
                   | self._adjust(-1, "2026-01-03 10:00:00")
                   | self._scrap(1, "2026-01-04 10:00:00"))
        order = self._purchase(price=200, quantity=2, date="2026-01-05 10:00:00")
        before = earlier.mapped("value")
        order._apply_purchase_cost_recompute()
        self.assertEqual(earlier.mapped("value"), before)

    def test_standard_fifo_boundary_excludes_gain_itself(self):
        self._purchase(price=100, quantity=5)
        gain = self._adjust(2, "2026-01-02 10:00:00")
        before = gain.date - timedelta(microseconds=1)
        historical = self.product.with_context(to_date=before)._with_valuation_context()
        self.assertEqual(historical.qty_available, 5)
        stack, first = self.product._run_fifo_get_stack(at_date=before)
        self.assertNotIn(gain, stack)
        self.assertEqual(first, 5)
