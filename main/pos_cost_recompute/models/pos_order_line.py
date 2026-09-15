import math

from odoo import fields, models
from odoo.exceptions import AccessError
from odoo.tools import float_compare, float_is_zero


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _cost_recompute_has_correction(self):
        orders = self.order_id
        if "correction_root_id" not in orders._fields:
            return False
        orders.check_access("read")
        return bool(orders.filtered(
            lambda order: order.correction_root_id or order.correction_ids
            or order.is_correction_order
        ))

    def _cost_recompute_unsupported_reason(self):
        self.ensure_one()
        if self.product_uom_id.is_zero(self.qty):
            return self.env._("Zero quantity is not supported.")
        if self.product_id.type == "combo" or self.combo_parent_id or self.combo_line_ids:
            return self.env._("POS combo structures require separate cost allocation.")
        if self._cost_recompute_has_correction():
            return self.env._("Project correction chains require separate cost allocation.")
        if "mrp.bom" in self.env:
            boms = self.env["mrp.bom"]._bom_find(
                self.product_id, company_id=self.company_id.id, bom_type="phantom"
            )
            if boms.get(self.product_id):
                return self.env._("Manufacturing kits require separate cost allocation.")
        return False

    def _cost_recompute_stock_source(self):
        """Keep the full product source when checking ambiguity and completion."""
        self.ensure_one()
        order = self.order_id
        pickings = order.picking_ids
        source = "order_moves"
        if not pickings:
            session = order.session_id
            if (not session.update_stock_at_closing or order.shipping_date
                    or order._force_create_picking_real_time()):
                return self.env["stock.move"], "", self.env._(
                    "No provable stock valuation source exists for this order."
                )
            source = "session_moves"
            if session.order_ids.lines._cost_recompute_has_correction():
                return self.env["stock.move"], source, self.env._(
                    "The shared session source is affected by project corrections."
                )
            pickings = session.picking_ids
        pickings.check_access("read")
        all_moves = pickings.move_ids
        all_moves.check_access("read")
        moves = self._get_stock_moves_to_consider(all_moves, self.product_id)
        if any(move.company_id != self.company_id for move in moves):
            raise AccessError(self.env._("Stock sources must belong to the order company."))
        active_moves = moves.filtered(lambda move: move.state != "cancel")
        if not active_moves:
            return moves, source, self.env._("No completed stock valuation source exists.")
        if any(move.state != "done" for move in active_moves):
            return moves, source, self.env._("Related stock processing is not complete.")
        incoming = active_moves.filtered("is_in")
        outgoing = active_moves.filtered("is_out")
        if incoming and outgoing:
            return moves, source, self.env._(
                "The stock source mixes sales and returns; its cost is ambiguous."
            )
        expected = outgoing if self.qty > 0 else incoming
        if expected != active_moves:
            return moves, source, self.env._("Stock source direction does not match the POS quantity.")
        if sum(move._get_valued_qty() for move in active_moves) <= 0:
            return moves, source, self.env._("The stock source has no positive valued quantity.")
        return moves, source, False

    def _prepare_cost_recompute_proposal(self, selected_lines):
        self.ensure_one()
        self.check_access("read")
        order = self.order_id
        order.check_access("read")
        order.session_id.check_access("read")
        product = self.product_id
        product.check_access("read")
        # Field-level restrictions matter even when product record access is granted.
        product.read(["standard_price", "cost_currency_id"])
        cost_currency = product.cost_currency_id
        currency = self.currency_id
        date = order.date_order or fields.Datetime.now()
        rate = cost_currency._get_conversion_rate(
            cost_currency, currency, self.company_id, date
        )
        related = (self.refunded_orderline_id | self.refund_orderline_ids) - selected_lines
        related.check_access("read")
        moves = self.env["stock.move"]
        source = "product"
        reason = self._cost_recompute_unsupported_reason()
        if not reason and order.state not in ("paid", "done"):
            reason = self.env._("Only paid or posted orders can be recomputed.")
        if not reason and order.session_id.state != "closed":
            reason = self.env._("The POS session is not closed.")
        if not reason and self._is_product_storable_fifo_avco():
            moves, source, reason = self._cost_recompute_stock_source()
        valued_moves = moves.filtered(lambda move: move.state == "done")
        unit_cost = 0.0
        if not reason:
            unit_cost = (self._get_product_cost_with_moves(valued_moves)
                         if valued_moves else product.standard_price)
            if not math.isfinite(unit_cost) or unit_cost < 0:
                reason = self.env._("A negative or non-finite unit cost is not supported.")
            elif valued_moves and order.shipping_date and cost_currency.is_zero(unit_cost):
                reason = self.env._("Deferred-delivery zero-cost substitution requires separate review.")
        proposed_cost = 0.0 if reason else self.qty * cost_currency._convert(
            unit_cost, currency, self.company_id, date, round=False
        )
        digits = self.env["decimal.precision"].precision_get("Product Price")
        status = "skipped"
        if not reason:
            if float_compare(self.total_cost, proposed_cost, precision_digits=digits):
                status = "changed"
            elif not self.is_total_cost_computed:
                status = "completion"
            else:
                status = "unchanged"
        zero_source = not reason and float_is_zero(unit_cost, precision_digits=digits)
        snapshot = {
            "line": [self.id, self.qty, self.total_cost, self.is_total_cost_computed,
                     self.price_subtotal, self.price_unit, self.discount,
                     self.product_uom_id.id, self.refunded_orderline_id.id],
            "order": [order.id, order.state, str(order.date_order), order.company_id.id,
                      order.config_id.id, str(order.shipping_date), order.is_refund,
                      order.currency_rate, order.account_move.id],
            "session": [order.session_id.id, order.session_id.state,
                        order.session_id.update_stock_at_closing],
            "product": [product.id, product.standard_price, product.cost_method,
                        product.is_storable, product.type, product.uom_id.id],
            "currency": [cost_currency.id, currency.id, rate, currency.rounding],
            "price_precision": digits,
            "source": source,
            "moves": [[m.id, m.state, m.company_id.id, m.value, m._get_valued_qty(),
                       m.is_in, m.is_out, m.origin_returned_move_id.id]
                      for m in moves.sorted("id")],
            "related": sorted(related.ids),
            "reason": reason or False,
            "proposed_cost": proposed_cost,
        }
        return {
            "pos_line_id": self.id,
            "company_id": self.company_id.id,
            "currency_id": currency.id,
            "product_id": product.id,
            "quantity": self.qty,
            "old_cost": self.total_cost,
            "new_cost": proposed_cost,
            "old_computed": self.is_total_cost_computed,
            "new_computed": self.is_total_cost_computed if reason else True,
            "status": status,
            "source": source or False,
            "skip_reason": reason or False,
            "zero_source": bool(zero_source),
            "snapshot": snapshot,
            "move_ids": [(6, 0, valued_moves.ids)],
            "related_line_ids": [(6, 0, related.ids)],
        }
