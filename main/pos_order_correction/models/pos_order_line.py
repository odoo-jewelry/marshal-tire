from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import float_compare

from .utils import is_internal_correction_call


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    correction_stock_qty = fields.Float(readonly=True, copy=False)
    correction_origin_line_id = fields.Many2one(
        "pos.order.line", readonly=True, copy=False, ondelete="restrict", check_company=True
    )
    correction_projection_line_id = fields.Many2one(
        "pos.order.correction.line", readonly=True, copy=False, ondelete="restrict", check_company=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        internal = is_internal_correction_call(self.env)
        protected = {"correction_stock_qty", "correction_origin_line_id", "correction_projection_line_id"}
        if not internal and (any(any(vals.get(field) for field in protected) for vals in vals_list)
                             or any(self.env.context.get("default_" + field) for field in protected)):
            raise UserError(self.env._("Correction line links can only be assigned by the correction workflow."))
        orders = self.env["pos.order"].browse([
            vals.get("order_id", self.env.context.get("default_order_id"))
            for vals in vals_list
            if vals.get("order_id", self.env.context.get("default_order_id"))
        ])
        if not internal:
            orders.filtered(lambda order: order.is_correction_order or order.correction_ids)._lock_correction_chain()
        if orders.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not internal:
            raise UserError(self.env._("Lines cannot be added to correction orders."))
        sources = self.browse([vals["refunded_orderline_id"] for vals in vals_list if vals.get("refunded_orderline_id")])
        if not internal:
            sources.order_id._lock_correction_chain()
        with self.env.cr.savepoint():
            lines = super().create(vals_list)
            if not internal:
                lines._check_correction_refund_quantities()
                lines.order_id._set_correction_return_root()
            return lines

    def _check_correction_refund_quantities(self):
        sources = self.refunded_orderline_id
        for source in sources:
            root = source.order_id._get_correction_root()
            if not root.correction_ids:
                continue
            root._lock_correction_chain()
            root._check_no_pending_correction_processing(
                self.env._("Close all correction sessions before returning products.")
            )
            if source not in root._get_effective_correction_lines():
                raise UserError(self.env._("This source was replaced by a correction. Reload the current sale before returning it."))
            source.invalidate_recordset(["refund_orderline_ids", "refunded_qty"])
            returns = source.refund_orderline_ids.filtered(
                lambda line: not line.order_id.is_correction_order and line.order_id.state != "cancel"
            )
            if any(line.qty >= 0.0 for line in returns) or float_compare(
                -sum(returns.mapped("qty")), source.qty,
                precision_rounding=source.product_uom_id.rounding,
            ) > 0:
                raise UserError(self.env._("The return exceeds the current unreturned quantity."))
            if source.product_id.tracking != "none":
                valid_names = set(source.pack_lot_ids.mapped("lot_name"))
                used_names = []
                for line in returns:
                    names = [name.strip() for name in line.pack_lot_ids.mapped("lot_name") if name]
                    if not names or not set(names).issubset(valid_names) or len(set(names)) != len(names):
                        raise UserError(self.env._("Return only lot or serial identities from the current sale."))
                    if source.product_id.tracking == "serial" and len(names) != -line.qty:
                        raise UserError(self.env._("The return quantity must match the selected serial numbers."))
                    used_names.extend(names)
                if source.product_id.tracking == "serial" and len(used_names) != len(set(used_names)):
                    raise UserError(self.env._("A serial number cannot be returned more than once."))

    def write(self, vals):
        internal = is_internal_correction_call(self.env)
        if {"correction_stock_qty", "correction_origin_line_id", "correction_projection_line_id"}.intersection(vals) and not internal:
            raise UserError(self.env._("Correction line links cannot be edited."))
        target = self.env["pos.order"].browse(vals.get("order_id", []))
        if not internal:
            (self.order_id | target).filtered(
                lambda order: order.is_correction_order or order.correction_ids
            )._lock_correction_chain()
        if target.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not internal:
            raise UserError(self.env._("Lines cannot be moved to correction orders."))
        if self.filtered(
            lambda line: line.order_id.is_correction_order or line.order_id.correction_ids.filtered(
                lambda correction: correction.state == "applied"
            )
        ) and not internal:
            raise UserError(self.env._("Applied correction order lines cannot be edited."))
        if not internal and {"qty", "refunded_orderline_id", "order_id"}.intersection(vals):
            sources = self.refunded_orderline_id | self.browse(vals.get("refunded_orderline_id", []))
            sources.order_id._lock_correction_chain()
            with self.env.cr.savepoint():
                result = super().write(vals)
                self._check_correction_refund_quantities()
                self.order_id._set_correction_return_root()
                return result
        return super().write(vals)

    def unlink(self):
        self.order_id.filtered(lambda order: order.is_correction_order or order.correction_ids)._lock_correction_chain()
        if self.filtered(lambda line: line.order_id.is_correction_order or line.order_id.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )):
            raise UserError(self.env._("Applied correction order lines cannot be deleted."))
        orders = self.order_id
        result = super().unlink()
        orders._set_correction_return_root()
        return result


class PosPackOperationLot(models.Model):
    _inherit = "pos.pack.operation.lot"

    @api.model_create_multi
    def create(self, vals_list):
        lines = self.env["pos.order.line"].browse([
            vals.get("pos_order_line_id", self.env.context.get("default_pos_order_line_id"))
            for vals in vals_list
            if vals.get("pos_order_line_id", self.env.context.get("default_pos_order_line_id"))
        ])
        if lines.order_id.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction lot identities cannot be edited."))
        return super().create(vals_list)

    def write(self, vals):
        lines = self.pos_order_line_id | self.env["pos.order.line"].browse(vals.get("pos_order_line_id", []))
        if lines.order_id.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction lot identities cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if self.pos_order_line_id.order_id.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )):
            raise UserError(self.env._("Correction lot identities cannot be deleted."))
        return super().unlink()


class ProductAttributeCustomValue(models.Model):
    _inherit = "product.attribute.custom.value"

    @api.model_create_multi
    def create(self, vals_list):
        lines = self.env["pos.order.line"].browse([
            vals.get("pos_order_line_id", self.env.context.get("default_pos_order_line_id"))
            for vals in vals_list
            if vals.get("pos_order_line_id", self.env.context.get("default_pos_order_line_id"))
        ])
        if lines.order_id.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction product attributes cannot be edited."))
        return super().create(vals_list)

    def write(self, vals):
        lines = self.pos_order_line_id | self.env["pos.order.line"].browse(vals.get("pos_order_line_id", []))
        if lines.order_id.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )) and not is_internal_correction_call(self.env):
            raise UserError(self.env._("Correction product attributes cannot be edited."))
        return super().write(vals)

    def unlink(self):
        if self.pos_order_line_id.order_id.filtered(lambda order: order.is_correction_order or order.correction_ids.filtered(
            lambda correction: correction.state == "applied"
        )):
            raise UserError(self.env._("Correction product attributes cannot be deleted."))
        return super().unlink()
