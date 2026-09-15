from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .pos_cost_recompute import _CONTEXT_KEY, _INTERNAL


_DIMENSIONS = {
    "product_id", "product_uom", "product_uom_qty", "quantity", "company_id",
    "location_id", "location_dest_id", "date", "state", "picked", "move_line_ids",
    "origin_returned_move_id",
    "picking_id", "product_qty", "is_in", "is_out", "is_dropship",
}


class StockMove(models.Model):
    _inherit = "stock.move"

    cost_repair_line_id = fields.Many2one(
        "pos.cost.recompute.stock.line", string="Stock Cost Repair", readonly=True,
        copy=False, check_company=True, ondelete="restrict", index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if any("cost_repair_line_id" in vals for vals in vals_list) or self.env.context.get(
            "default_cost_repair_line_id"
        ):
            raise AccessError(self.env._("Stock repair links are server-managed."))
        return super().create(vals_list)

    def write(self, vals):
        internal = self.env.context.get(_CONTEXT_KEY) is _INTERNAL
        if "cost_repair_line_id" in vals and not internal:
            raise AccessError(self.env._("Stock repair links are server-managed."))
        if not internal and set(vals) & (_DIMENSIONS | {"value", "value_manual"}):
            if self.filtered("cost_repair_line_id"):
                raise UserError(self.env._(
                    "This movement has a reviewed stock cost repair. Changing its value or "
                    "stock dimensions requires a separate traceable correction."
                ))
        return super().write(vals)

    def unlink(self):
        if self.filtered("cost_repair_line_id"):
            raise UserError(self.env._("Repaired stock movements cannot be deleted."))
        return super().unlink()

    def _set_value(self, correction_quantity=None):
        repaired = self.filtered("cost_repair_line_id")
        for move in repaired:
            detail = move.cost_repair_line_id
            if correction_quantity or not move.is_out or move.state != "done" or (
                move.company_id != detail.company_id
                or move.product_id != detail.product_id
                or move.product_id.uom_id.compare(move._get_valued_qty(), detail.quantity)
                or move.value != detail.new_value
            ):
                raise UserError(self.env._("The repaired movement requires a separate traceable correction."))
        return super(StockMove, self - repaired)._set_value(correction_quantity=correction_quantity)


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        move_ids = {vals.get("move_id", self.env.context.get("default_move_id")) for vals in vals_list}
        if self.env["stock.move"].browse([item for item in move_ids if item]).filtered("cost_repair_line_id"):
            raise UserError(self.env._("Lines of repaired stock movements cannot be changed."))
        return super().create(vals_list)

    def write(self, vals):
        dimensions = {"move_id", "product_id", "product_uom_id", "quantity", "picked", "lot_id",
                      "quantity_product_uom", "state", "date", "owner_id", "location_id",
                      "location_dest_id", "company_id", "quant_id"}
        moves = self.move_id | self.env["stock.move"].browse(vals.get("move_id", []))
        if set(vals) & dimensions and moves.filtered("cost_repair_line_id"):
            raise UserError(self.env._("Lines of repaired stock movements cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if self.move_id.filtered("cost_repair_line_id"):
            raise UserError(self.env._("Lines of repaired stock movements cannot be deleted."))
        return super().unlink()


class ProductValue(models.Model):
    _inherit = "product.value"

    @api.model_create_multi
    def create(self, vals_list):
        move_ids = {vals.get("move_id", self.env.context.get("default_move_id")) for vals in vals_list}
        if self.env["stock.move"].browse([item for item in move_ids if item]).filtered("cost_repair_line_id"):
            raise UserError(self.env._("A repaired movement requires a separate traceable revaluation."))
        return super().create(vals_list)

    def write(self, vals):
        moves = self.move_id | self.env["stock.move"].browse(vals.get("move_id", []))
        if moves.filtered("cost_repair_line_id"):
            raise UserError(self.env._("A repaired movement requires a separate traceable revaluation."))
        return super().write(vals)
