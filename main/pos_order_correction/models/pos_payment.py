from odoo import api, models
from odoo.exceptions import UserError

from .utils import is_internal_correction_call


class PosPayment(models.Model):
    _inherit = "pos.payment"

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env["pos.order"].browse([
            vals.get("pos_order_id", self.env.context.get("default_pos_order_id"))
            for vals in vals_list
            if vals.get("pos_order_id", self.env.context.get("default_pos_order_id"))
        ])
        if not is_internal_correction_call(self.env):
            orders.filtered(lambda order: order.is_correction_order or order.correction_ids)._lock_correction_chain()
        if orders.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Payments cannot be added to correction orders."))
        return super().create(vals_list)

    def write(self, vals):
        target = self.env["pos.order"].browse(vals.get("pos_order_id", []))
        if not is_internal_correction_call(self.env):
            (self.pos_order_id | target).filtered(
                lambda order: order.is_correction_order or order.correction_ids
            )._lock_correction_chain()
        if target.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Payments cannot be moved to correction orders."))
        if self.filtered(
            lambda payment: payment.pos_order_id.is_correction_order or payment.pos_order_id.correction_ids.filtered(
                lambda correction: correction.state == "applied"
            )
        ) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Applied correction payments cannot be edited."))
        return super().write(vals)

    def unlink(self):
        self.pos_order_id.filtered(lambda order: order.is_correction_order or order.correction_ids)._lock_correction_chain()
        if self.filtered(lambda payment: payment.pos_order_id.is_correction_order or payment.pos_order_id.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )):
            raise UserError(self.env._("Applied correction payments cannot be deleted."))
        return super().unlink()
