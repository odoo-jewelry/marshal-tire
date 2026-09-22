from odoo import models

from .product_product import _CONTEXT_KEY, _INTERNAL


_POS_LINE_IDS_KEY = "_purchase_cost_recompute_pos_line_ids"
_COMPANY_KEY = "_purchase_cost_recompute_company_id"


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    def _get_stock_moves_to_consider(self, stock_moves, product):
        moves = super()._get_stock_moves_to_consider(stock_moves, product)
        if (self.env.context.get(_CONTEXT_KEY) is not _INTERNAL
                or self.env.company != self.company_id):
            return moves
        # Stock loss on the same picking is not a unit sold by this POS line.
        return moves.filtered(
            lambda move: not (move.location_dest_id.usage == "inventory"
                              and (move.is_inventory or move.scrap_id))
        )

    def _is_product_storable_fifo_avco(self):
        if super()._is_product_storable_fifo_avco():
            return True
        context = self.env.context
        # Only the current prevalidated source group may opt into historical
        # valuation. RPC context cannot reproduce the identity token.
        return (
            context.get(_CONTEXT_KEY) is _INTERNAL
            and context.get(_COMPANY_KEY) == self.env.company.id == self.company_id.id
            and context.get("allowed_company_ids") == [self.company_id.id]
            and self.id in context.get(_POS_LINE_IDS_KEY, ())
            and not self.product_id.is_storable
            and self.product_id.type == "consu"
            and self.product_id.cost_method == "fifo"
        )
