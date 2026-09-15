from dateutil.relativedelta import relativedelta

from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionStock(PosOrderCorrectionCommon):
    def test_product_replacement_moves_only_difference(self):
        order = self._create_paid_order("correction-stock-1")
        original_move = (order.picking_ids.move_ids | order.stock_reference_ids.move_ids).filtered(
            lambda move: move.product_id == self.product100 and move.state == "done"
        )
        correction = self._prepare(order)
        correction.line_ids.product_id = self.product80
        correction.line_ids.price_unit = 80
        correction.payment_ids.amount = 80
        correction.reason = "Wrong product"
        correction.action_apply()

        moves = correction.applied_order_id.picking_ids.move_ids
        returned = moves.filtered(lambda move: move.product_id == self.product100)
        delivered = moves.filtered(lambda move: move.product_id == self.product80)
        self.assertEqual(returned.product_uom_qty, 1)
        self.assertEqual(returned.origin_returned_move_id, original_move)
        self.assertEqual(delivered.product_uom_qty, 1)
        self.assertFalse(delivered.origin_returned_move_id)
        self.assertTrue(all(move.state == "done" for move in moves))

    def test_quantity_decrease_returns_only_delta(self):
        order = self._create_paid_order("correction-stock-2")
        correction = self._prepare(order)
        correction.line_ids.qty = 0.5
        correction.payment_ids.amount = 50
        correction.reason = "Wrong quantity"
        correction.action_apply()

        moves = correction.applied_order_id.picking_ids.move_ids
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.product_id, self.product100)
        self.assertEqual(moves.product_uom_qty, 0.5)
        self.assertTrue(moves.origin_returned_move_id)

    def test_same_session_closing_moves_final_product_once(self):
        self.company.point_of_sale_update_stock_quantities = "closing"
        order = self._create_paid_order("correction-stock-closing-1")
        correction = self._prepare(order)
        correction.line_ids.product_id = self.product80
        correction.line_ids.price_unit = 80
        correction.payment_ids.amount = 80
        correction.reason = "Wrong product before session closure"
        correction.action_apply()
        self.assertFalse(order.picking_ids | correction.applied_order_id.picking_ids)

        self._close_session(self.session)

        moves = self.session.picking_ids.move_ids.filtered(lambda move: move.state == "done")
        self.assertFalse(moves.filtered(lambda move: move.product_id == self.product100))
        delivered = moves.filtered(lambda move: move.product_id == self.product80)
        self.assertEqual(delivered.product_uom_qty, 1)
        self.assertIn(
            delivered,
            correction.applied_order_id.stock_reference_ids.move_ids,
        )

    def test_replacement_after_price_correction_uses_original_move(self):
        order = self._create_paid_order("correction-stock-price-then-product")
        original_move = order.picking_ids.move_ids.filtered(
            lambda move: move.product_id == self.product100
        )
        price = self._prepare(order)
        price.line_ids.price_unit = 110
        price.payment_ids.amount = 110
        price.reason = "Wrong price"
        price.action_apply()
        self.assertFalse(price.applied_order_id.picking_ids)

        product = self._prepare(order)
        product.line_ids.product_id = self.product80
        product.line_ids.price_unit = 80
        product.payment_ids.amount = 80
        product.reason = "Wrong product"
        product.action_apply()

        returned = product.applied_order_id.picking_ids.move_ids.filtered(
            lambda move: move.product_id == self.product100
        )
        self.assertEqual(returned.origin_returned_move_id, original_move)

    def test_undelivered_quantity_reduces_pending_demand(self):
        self.config.ship_later = True
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders(
            [
                {
                    "pos_order_lines_ui_args": [(self.product100, 3)],
                    "payments": [(self.cash_pm1, 300)],
                    "customer": self.customer,
                    "uuid": "correction-stock-pending",
                    "pos_order_ui_args": {
                        "shipping_date": fields.Date.to_string(
                            fields.Date.today() + relativedelta(days=1)
                        )
                    },
                }
            ]
        )["correction-stock-pending"]
        pending_move = order.picking_ids.move_ids.filtered(
            lambda move: move.product_id == self.product100
        )
        self.assertEqual(pending_move.product_uom_qty, 3)

        correction = self._prepare(order)
        correction.line_ids.qty = 2
        correction.payment_ids.amount = 200
        correction.reason = "Wrong undelivered quantity"
        correction.action_apply()

        self.assertEqual(pending_move.product_uom_qty, 2)
        self.assertFalse(correction.applied_order_id.picking_ids)

    def _correct_quantity(self, order, quantity):
        correction = self._prepare(order)
        correction.line_ids.qty = quantity
        correction.payment_ids.amount = quantity * correction.line_ids.price_unit
        correction.reason = "Correct quantity"
        correction.action_apply()
        return correction

    def _pay_refund(self, refund):
        payment = self.env["pos.make.payment"].with_context(
            active_ids=refund.ids, active_id=refund.id
        ).create({
            "payment_method_id": self.cash_pm1.id,
            "amount": refund.amount_total,
        })
        payment.check()

    def test_closing_price_then_replacement_moves_only_final_product(self):
        self.company.point_of_sale_update_stock_quantities = "closing"
        order = self._create_paid_order("stock-closing-price-product")
        price = self._prepare(order)
        price.line_ids.price_unit = 110
        price.payment_ids.amount = 110
        price.reason = "Correct price"
        price.action_apply()
        replacement = self._prepare(order)
        replacement.line_ids.product_id = self.product80
        replacement.line_ids.price_unit = 80
        replacement.payment_ids.amount = 80
        replacement.reason = "Correct product"
        replacement.action_apply()

        self._close_session(self.session)

        moves = self.session.picking_ids.move_ids.filtered(lambda move: move.state == "done")
        self.assertFalse(moves.filtered(lambda move: move.product_id == self.product100))
        delivered = moves.filtered(lambda move: move.product_id == self.product80)
        self.assertEqual(sum(delivered.mapped("quantity")), 1)
        self.assertFalse(moves.origin_returned_move_id)

    def test_closing_preserves_unrelated_ordinary_return(self):
        self.company.point_of_sale_update_stock_quantities = "closing"
        ordinary = self._create_paid_order("stock-closing-ordinary-source")
        self._close_session(self.session)
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        refund = ordinary._refund()
        self._pay_refund(refund)
        corrected = self._create_paid_order("stock-closing-unrelated-correction")
        price = self._prepare(corrected)
        price.line_ids.price_unit = 110
        price.payment_ids.amount = 110
        price.reason = "Correct another sale"
        price.action_apply()

        self._close_session(self.session)

        moves = self.session.picking_ids.move_ids.filtered(lambda move: move.state == "done")
        incoming = moves.filtered(lambda move: move.location_id.usage == "customer")
        outgoing = moves.filtered(lambda move: move.location_dest_id.usage == "customer")
        self.assertEqual(sum(incoming.mapped("quantity")), 1)
        self.assertEqual(sum(outgoing.mapped("quantity")), 1)

    def test_closing_two_revisions_of_closed_source_do_not_move_intermediate_product(self):
        self.company.point_of_sale_update_stock_quantities = "closing"
        order = self._create_paid_order("stock-closing-external-chain")
        self._close_session(self.session)
        original_move = order.stock_reference_ids.move_ids.filtered(
            lambda move: move.location_dest_id.usage == "customer"
        )
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        replacement = self._prepare(order)
        replacement.line_ids.product_id = self.product80
        replacement.line_ids.price_unit = 80
        replacement.payment_ids.amount = 80
        replacement.reason = "Correct product"
        replacement.action_apply()
        restored = self._prepare(order)
        restored.line_ids.product_id = self.product100
        restored.line_ids.price_unit = 100
        restored.payment_ids.amount = 100
        restored.reason = "Restore product"
        restored.action_apply()

        self._close_session(self.session)

        moves = self.session.picking_ids.move_ids.filtered(lambda move: move.state == "done")
        self.assertFalse(moves.filtered(lambda move: move.product_id == self.product80))
        returned = moves.filtered(lambda move: move.origin_returned_move_id)
        self.assertEqual(returned.origin_returned_move_id, original_move)
        self.assertEqual(returned.quantity, 1)

    def test_quantity_increase_then_return_uses_both_deliveries(self):
        order = self._create_paid_order("stock-quantity-increase-return")
        original_move = order.picking_ids.move_ids
        increase = self._correct_quantity(order, 2)
        increased_move = increase.applied_order_id.picking_ids.move_ids
        self.assertEqual(increased_move.quantity, 1)
        self._close_session(self.session)
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )

        refund = order._refund()
        self._pay_refund(refund)

        returned = refund.picking_ids.move_ids
        self.assertEqual(sum(returned.mapped("quantity")), 2)
        self.assertEqual(returned.origin_returned_move_id, original_move | increased_move)

    def test_ordinary_return_after_price_correction_preserves_historical_move(self):
        order = self._create_paid_order("stock-return-after-price")
        original_move = order.picking_ids.move_ids
        price = self._prepare(order)
        price.line_ids.price_unit = 120
        price.payment_ids.amount = 120
        price.reason = "Correct price"
        price.action_apply()
        self._close_session(self.session)
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )

        refund = order._refund()
        self._pay_refund(refund)

        self.assertEqual(refund.picking_ids.move_ids.origin_returned_move_id, original_move)
        self.assertEqual(refund.picking_ids.move_ids.quantity, 1)

    def test_pending_delivery_increase_keeps_additional_demand_pending(self):
        self.config.ship_later = True
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders([{
            "pos_order_lines_ui_args": [(self.product100, 3)],
            "payments": [(self.cash_pm1, 300)],
            "customer": self.customer,
            "uuid": "stock-pending-increase",
            "pos_order_ui_args": {"shipping_date": fields.Date.to_string(
                fields.Date.today() + relativedelta(days=1)
            )},
        }])["stock-pending-increase"]

        increase = self._correct_quantity(order, 4)

        moves = (order | increase.applied_order_id).picking_ids.move_ids.filtered(
            lambda move: move.state != "cancel" and move.location_dest_id.usage == "customer"
        )
        self.assertEqual(sum(moves.mapped("product_uom_qty")), 4)
        self.assertFalse(moves.filtered(lambda move: move.state == "done"))
        self.assertEqual(increase.applied_order_id.picking_ids.move_ids.product_uom_qty, 1)

    def test_partial_delivery_decrease_only_reduces_backorder(self):
        self.config.ship_later = True
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders([{
            "pos_order_lines_ui_args": [(self.product100, 3)],
            "payments": [(self.cash_pm1, 300)],
            "customer": self.customer,
            "uuid": "stock-partial-delivery",
            "pos_order_ui_args": {"shipping_date": fields.Date.to_string(
                fields.Date.today() + relativedelta(days=1)
            )},
        }])["stock-partial-delivery"]
        picking = order.picking_ids
        picking.move_ids.quantity = 1
        picking.move_ids.picked = True
        picking._action_done()
        completed = order.picking_ids.move_ids.filtered(lambda move: move.state == "done")
        pending = order.picking_ids.move_ids.filtered(lambda move: move.state not in ("done", "cancel"))
        self.assertEqual(completed.quantity, 1)
        self.assertEqual(pending.product_uom_qty, 2)

        correction = self._correct_quantity(order, 2)

        self.assertEqual(completed.quantity, 1)
        self.assertEqual(pending.product_uom_qty, 1)
        self.assertFalse(correction.applied_order_id.picking_ids)

    def _create_serial_order(self, shipping=False):
        self.product100.tracking = "serial"
        self.config.ship_later = shipping
        lots = self.env["stock.lot"].create([
            {"name": name, "product_id": self.product100.id, "company_id": self.company.id}
            for name in ("COR-SERIAL-1", "COR-SERIAL-2", "COR-SERIAL-3")
        ])
        self.env["stock.quant"].with_context(inventory_mode=True).create([
            {
                "product_id": self.product100.id,
                "location_id": self.config.picking_type_id.default_location_src_id.id,
                "lot_id": lot.id,
                "inventory_quantity": 1,
            } for lot in lots
        ]).action_apply_inventory()
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders([{
            "pos_order_lines_ui_args": [{
                "product": self.product100,
                "quantity": 3,
                "pack_lot_ids": [Command.create({"lot_name": lot.name}) for lot in lots],
            }],
            "payments": [(self.cash_pm1, 300)],
            "customer": self.customer,
            "uuid": "stock-serial-decrease",
            "pos_order_ui_args": {"shipping_date": fields.Date.to_string(
                fields.Date.today() + relativedelta(days=1)
            )} if shipping else {},
        }])["stock-serial-decrease"]
        return order, lots

    def test_serial_decrease_returns_only_removed_serial(self):
        order, lots = self._create_serial_order()
        correction = self._prepare(order)
        correction.line_ids.qty = 2
        correction.line_ids.lot_names = "COR-SERIAL-1\nCOR-SERIAL-2"
        correction.payment_ids.amount = 200
        correction.reason = "Remove third serial"

        correction.action_apply()

        returned = correction.applied_order_id.picking_ids.move_ids
        self.assertEqual(returned.quantity, 1)
        self.assertEqual(returned.move_line_ids.lot_id, lots[2])
        self.assertEqual(returned.origin_returned_move_id, order.picking_ids.move_ids)

    def test_stock_failure_rolls_back_operational_documents(self):
        order = self._create_paid_order("stock-failed-movement")
        correction = self._prepare(order)
        correction.line_ids.product_id = self.product80
        correction.line_ids.price_unit = 80
        correction.payment_ids.amount = 80
        correction.reason = "Correct product"
        order_count = self.env["pos.order"].search_count([])
        picking_count = self.env["stock.picking"].search_count([])
        with patch.object(type(self.env["stock.picking"]), "_action_done", side_effect=UserError("Stock failure")):
            with self.assertRaises(UserError), self.env.cr.savepoint():
                correction.action_apply()
        self.assertEqual(correction.state, "draft")
        self.assertFalse(correction.applied_order_id)
        self.assertEqual(self.env["pos.order"].search_count([]), order_count)
        self.assertEqual(self.env["stock.picking"].search_count([]), picking_count)

    def test_avco_return_and_chain_margin_preserve_historical_cost(self):
        average_category = self.categ_basic.copy({
            "name": "Correction average cost",
            "property_cost_method": "average",
            "property_valuation": "real_time",
        })
        self.product100.categ_id = average_category
        order = self._create_paid_order("stock-historical-cost")
        original_move = order.picking_ids.move_ids
        original_value = abs(original_move.value)
        self.assertEqual(original_value, 50)
        self.product100.standard_price = 70
        price = self._prepare(order)
        price.line_ids.price_unit = 120
        price.payment_ids.amount = 120
        price.reason = "Correct price after cost changed"
        price.action_apply()
        self.assertFalse(price.applied_order_id.picking_ids)
        chain = order._get_correction_chain()
        self.assertEqual(sum(chain.lines.mapped("total_cost")), 50)
        self.assertEqual(sum(chain.mapped("margin")), 70)

        replacement = self._prepare(order)
        replacement.line_ids.product_id = self.product80
        replacement.line_ids.price_unit = 80
        replacement.payment_ids.amount = 80
        replacement.reason = "Replace product after price correction"
        replacement.action_apply()
        returned = replacement.applied_order_id.picking_ids.move_ids.filtered(
            lambda move: move.origin_returned_move_id
        )
        self.assertEqual(returned.origin_returned_move_id, original_move)
        self.assertEqual(abs(returned.value), original_value)
        self._close_session(self.session)
        chain = order._get_correction_chain()
        self.assertEqual(sum(chain.lines.mapped("total_cost")), 40)
        self.assertEqual(sum(chain.mapped("margin")), 40)

    def test_lot_change_moves_old_and_new_lots_without_quantity_change(self):
        self.product100.tracking = "lot"
        lots = self.env["stock.lot"].create([
            {"name": name, "product_id": self.product100.id, "company_id": self.company.id}
            for name in ("COR-LOT-OLD", "COR-LOT-NEW")
        ])
        self.env["stock.quant"].with_context(inventory_mode=True).create([
            {
                "product_id": self.product100.id,
                "location_id": self.config.picking_type_id.default_location_src_id.id,
                "lot_id": lot.id,
                "inventory_quantity": 1,
            } for lot in lots
        ]).action_apply_inventory()
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders([{
            "pos_order_lines_ui_args": [{
                "product": self.product100,
                "quantity": 1,
                "pack_lot_ids": [Command.create({"lot_name": lots[0].name})],
            }],
            "payments": [(self.cash_pm1, 100)],
            "customer": self.customer,
            "uuid": "stock-lot-replacement",
        }])["stock-lot-replacement"]
        correction = self._prepare(order)
        correction.line_ids.lot_names = lots[1].name
        correction.reason = "Correct recorded lot"

        correction.action_apply()

        moves = correction.applied_order_id.picking_ids.move_ids
        returned = moves.filtered(lambda move: move.origin_returned_move_id)
        delivered = moves - returned
        self.assertEqual(returned.quantity, 1)
        self.assertEqual(returned.move_line_ids.lot_id, lots[0])
        self.assertEqual(returned.origin_returned_move_id, order.picking_ids.move_ids)
        self.assertEqual(delivered.quantity, 1)
        self.assertEqual(delivered.move_line_ids.lot_id, lots[1])

    def test_pending_serial_decrease_preserves_remaining_reservations(self):
        order, lots = self._create_serial_order(shipping=True)
        correction = self._prepare(order)
        correction.line_ids.qty = 2
        correction.line_ids.lot_names = "COR-SERIAL-1\nCOR-SERIAL-2"
        correction.payment_ids.amount = 200
        correction.reason = "Remove undelivered third serial"

        correction.action_apply()

        pending = order.picking_ids.move_ids.filtered(lambda move: move.state != "cancel")
        self.assertEqual(pending.product_uom_qty, 2)
        self.assertEqual(pending.move_line_ids.lot_id, lots[:2])
        self.assertFalse(pending.filtered(lambda move: move.state == "done"))
        self.assertFalse(correction.applied_order_id.picking_ids)

    def test_pending_replacement_retains_shipping_date_and_demand(self):
        self.config.ship_later = True
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        order = self._create_orders([{
            "pos_order_lines_ui_args": [(self.product100, 3)],
            "payments": [(self.cash_pm1, 300)],
            "customer": self.customer,
            "uuid": "stock-pending-replacement",
            "pos_order_ui_args": {"shipping_date": fields.Date.to_string(
                fields.Date.today() + relativedelta(days=2)
            )},
        }])["stock-pending-replacement"]
        source_deadline = order.picking_ids.move_ids.date_deadline
        correction = self._prepare(order)
        correction.line_ids.product_id = self.product80
        correction.line_ids.price_unit = 80
        correction.payment_ids.amount = 240
        correction.reason = "Replace undelivered product"

        correction.action_apply()

        self.assertEqual(order.picking_ids.state, "cancel")
        replacement = correction.applied_order_id.picking_ids.move_ids
        self.assertEqual(replacement.product_id, self.product80)
        self.assertEqual(replacement.product_uom_qty, 3)
        self.assertEqual(replacement.date_deadline, source_deadline)
        self.assertNotEqual(replacement.state, "done")

    def test_unprovable_stock_source_is_rejected_during_preparation(self):
        order = self._create_paid_order("stock-unprovable-source")
        historical_picking = order.picking_ids
        historical_picking.pos_order_id = False
        self.assertFalse(order.picking_ids | order.stock_reference_ids.move_ids.picking_id)

        with self.assertRaises(UserError):
            order.action_prepare_correction()

        self.assertFalse(order.correction_ids)
        self.assertEqual(historical_picking.state, "done")
        self.assertEqual(historical_picking.move_ids.quantity, 1)

    def test_client_context_cannot_override_stock_quantities_or_sources(self):
        original = self._create_paid_order("stock-client-context-source")
        copied = original.copy({
            "state": "draft", "payment_ids": [Command.clear()], "amount_paid": 0,
        })
        copied._compute_prices()
        malicious_context = {
            "active_ids": copied.ids,
            "active_id": copied.id,
            "pos_order_correction_internal": True,
            "pos_order_correction_stock": True,
            "pos_order_correction_stock_quantities": {copied.lines.id: 7},
            "pos_order_correction_stock_lots": {copied.lines.id: ["FORGED-SERIAL"]},
            "pos_order_correction_source_move_id": original.picking_ids.move_ids.id,
            "pos_order_correction_closing_quantities": {copied.lines.id: 0},
            "pos_order_correction_closing_lots": {copied.lines.id: []},
            "pos_order_correction_link_closing_sources": True,
            "pos_order_correction_stock_context": [True, {
                "mode": "move", "quantities": {copied.lines.id: 7},
                "lot_names": {copied.lines.id: ["FORGED-SERIAL"]},
                "source_move_id": original.picking_ids.move_ids.id,
            }],
        }
        payment = self.env["pos.make.payment"].with_context(**malicious_context).create({
            "payment_method_id": self.cash_pm1.id,
            "amount": copied.amount_total,
        })

        payment.check()

        self.assertEqual(copied.picking_ids.move_ids.quantity, 1)
        self.assertFalse(copied.picking_ids.move_ids.origin_returned_move_id)
        correction = self._prepare(copied)
        correction.line_ids.qty = 0.5
        correction.payment_ids.amount = 50
        correction.reason = "Correct quantity despite untrusted client context"
        malicious_context["pos_order_correction_session_closing"] = True
        correction.with_context(**malicious_context).action_apply()
        returned = correction.applied_order_id.picking_ids.move_ids
        self.assertEqual(returned.quantity, 0.5)
        self.assertEqual(returned.origin_returned_move_id, copied.picking_ids.move_ids)
