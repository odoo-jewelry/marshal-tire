from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .pos_cost_recompute import _CONTEXT_KEY, _INTERNAL


class PosCostRecomputeStockLine(models.Model):
    _name = "pos.cost.recompute.stock.line"
    _description = "Reviewed POS Stock Value Repair"
    _check_company_auto = True
    _rec_name = "move_id"

    operation_id = fields.Many2one("pos.cost.recompute", required=True, check_company=True, ondelete="restrict")
    company_id = fields.Many2one("res.company", required=True)
    currency_id = fields.Many2one("res.currency", required=True)
    move_id = fields.Many2one("stock.move", required=True, check_company=True, ondelete="restrict")
    receipt_id = fields.Many2one("stock.move", check_company=True, ondelete="restrict")
    product_id = fields.Many2one("product.product", required=True, check_company=True, ondelete="restrict")
    quantity = fields.Float(readonly=True)
    old_value = fields.Monetary(readonly=True)
    new_value = fields.Monetary(readonly=True)
    actual_value = fields.Monetary(readonly=True)
    status = fields.Selection([("repair", "Stock Value Repair"), ("skipped", "Skipped")], required=True)
    skip_reason = fields.Text(readonly=True)
    warning = fields.Text(readonly=True)
    snapshot = fields.Json(readonly=True)
    pos_line_ids = fields.Many2many("pos.order.line", readonly=True, check_company=True)

    _unique_move = models.Constraint("UNIQUE(operation_id, move_id)", "A stock issue must appear only once per operation.")

    def _check_internal(self):
        self.env["pos.cost.recompute"]._check_manager()
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(self.env._("Stock repair requires POS-manager and stock-manager permissions."))
        if self.env.context.get(_CONTEXT_KEY) is not _INTERNAL:
            raise AccessError(self.env._("Stock repair evidence is server-managed."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_internal()
        return super().create(vals_list)

    def write(self, vals):
        self._check_internal()
        if self.operation_id.filtered(lambda op: op.state in ("done", "cancelled")):
            raise UserError(self.env._("Applied or cancelled stock repair evidence cannot be edited."))
        return super().write(vals)

    def unlink(self):
        self._check_internal()
        if self.operation_id.filtered(lambda op: op.state == "done"):
            raise UserError(self.env._("Applied stock repair evidence cannot be deleted."))
        return super().unlink()

    def _apply_reviewed_value(self):
        self.ensure_one()
        self.operation_id._check_manager()
        if self.operation_id.state != "ready" or self.status != "repair":
            raise UserError(self.env._("Only a current reviewed stock repair can be applied."))
        move = self.move_id
        move.check_access("write")
        if move.cost_repair_line_id or not self.currency_id.is_zero(move.value):
            raise UserError(self.env._("The stock repair preview is stale."))
        move.with_context(**{_CONTEXT_KEY: _INTERNAL}).write({
            "value": self.new_value, "cost_repair_line_id": self.id,
        })
        self.with_context(**{_CONTEXT_KEY: _INTERNAL}).write({"actual_value": move.value})


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    cost_recompute_revision = fields.Integer(default=0, readonly=True, copy=False)

    def write(self, vals):
        if vals.get("state") == "to remove":
            self._check_pos_stock_repair_removal()
        return super().write(vals)

    def _check_pos_stock_repair_removal(self):
        if "pos_cost_recompute" in self.mapped("name") and self.env[
            "stock.move"
        ].sudo().search_count([("cost_repair_line_id", "!=", False)], limit=1):
            # Module removal is global. Check all companies, including ones
            # outside the administrator's current company selection.
            raise UserError(self.env._("POS Cost Recompute cannot be removed while applied stock repairs exist."))

    def button_uninstall(self):
        (self | self.downstream_dependencies())._check_pos_stock_repair_removal()
        return super().button_uninstall()

    def module_uninstall(self):
        self._check_pos_stock_repair_removal()
        return super().module_uninstall()
