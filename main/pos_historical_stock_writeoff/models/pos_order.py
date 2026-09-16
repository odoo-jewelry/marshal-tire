import hashlib
import json

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError

from .history import _INTERNAL, _KEY, check_permission


class PosOrder(models.Model):
    _inherit = "pos.order"

    historical_picking_ids = fields.One2many(
        "stock.picking", "historical_pos_order_id", string="Historical Stock Write-offs", copy=False,
    )

    def _check_no_historical_processing(self):
        if not self:
            return
        self.check_access("read")
        self.sorted("id").lock_for_update()
        self.invalidate_recordset(["historical_picking_ids"])
        if self.historical_picking_ids.filtered(lambda picking: picking.state != "cancel"):
            raise UserError(self.env._("A receipt used for historical stock consumption cannot create another payment, delivery or return."))

    def _create_order_picking(self):
        self._check_no_historical_processing()
        return super()._create_order_picking()

    def _historical_source_snapshot(self):
        self.ensure_one()
        return hashlib.sha256(json.dumps({
            "order": self.read(["state", "date_order", "session_id", "partner_id"]),
            "lines": self.lines.sorted("id").read(["product_id", "qty", "price_unit", "discount"]),
        }, sort_keys=True, default=str).encode()).hexdigest()

    def _check_historical_source(self):
        self.check_access("read")
        for order in self:
            if order.company_id not in self.env.companies:
                raise AccessError(self.env._("The source company is not allowed."))
            if (order.state not in ("draft", "cancel") or order.payment_ids or order.account_move
                    or order.picking_ids or order.stock_reference_ids or order.correction_ids
                    or order.is_correction_order or order.correction_root_id or order.correction_return_root_id
                    or order.lines.refunded_orderline_id or order.lines.refund_orderline_ids
                    or order.debt_allocation_ids):
                raise UserError(self.env._("Historical stock preparation requires a draft or cancelled receipt without payments, deliveries, invoices, returns, corrections or debt settlement."))

    def action_prepare_historical_stock(self):
        self.ensure_one()
        check_permission(self.env)
        self.check_access("write")
        self.lock_for_update()
        self.invalidate_recordset()
        existing = self.historical_picking_ids.filtered(lambda picking: picking.state != "cancel")
        if existing:
            existing.check_access("read")
            return existing._historical_action()
        self._check_historical_source()
        lines = self.lines.filtered(lambda line: line.product_id.is_storable)
        if not lines:
            raise UserError(self.env._("The receipt contains no stock products."))
        operation_type = self.config_id.picking_type_id
        if operation_type.code != "outgoing" or operation_type.default_location_src_id.usage != "internal":
            raise UserError(self.env._("Historical consumption requires a direct delivery operation."))
        location = operation_type.default_location_src_id
        destination = self.env.ref("stock.stock_location_customers")
        picking = self.env["stock.picking"].with_context(**{_KEY: _INTERNAL}).create({
            "picking_type_id": operation_type.id,
            "location_id": location.id,
            "location_dest_id": destination.id,
            "company_id": self.company_id.id,
            "partner_id": self.partner_id.id,
            "historical_pos_order_id": self.id,
            "historical_source_snapshot": self._historical_source_snapshot(),
            "origin": self.pos_reference or self.name,
            "move_ids": [Command.create({
                "product_id": line.product_id.id,
                "product_uom": line.product_id.uom_id.id,
                "product_uom_qty": line.qty,
                "location_id": location.id,
                "location_dest_id": destination.id,
                "company_id": self.company_id.id,
            }) for line in lines],
        })
        return picking._historical_action()

    def action_view_historical_stock(self):
        self.check_access("read")
        self.historical_picking_ids.check_access("read")
        return {"type": "ir.actions.act_window", "name": self.env._("Historical Stock Write-offs"),
                "res_model": "stock.picking", "view_mode": "list,form",
                "domain": [("id", "in", self.historical_picking_ids.ids)]}

    def action_view_cost_recomputations(self):
        action = super().action_view_cost_recomputations()
        action["domain"] = ["|", ("line_ids.pos_line_id.order_id", "in", self.ids),
                            ("historical_picking_ids.historical_pos_order_id", "in", self.ids)]
        return action

    def action_prepare_cost_recompute(self):
        completed = self.historical_picking_ids.filtered(lambda picking: picking.state == "done")
        if completed:
            if any(not order.historical_picking_ids.filtered(lambda picking: picking.state == "done") for order in self):
                raise UserError(self.env._("Select historical source receipts separately from ordinary sales."))
            return completed.action_prepare_historical_recompute()
        return super().action_prepare_cost_recompute()

    def write(self, vals):
        if set(vals) & {"state", "session_id", "company_id", "account_move", "lines", "payment_ids", "date_order", "partner_id"}:
            self.check_access("write")
            self.sorted("id").lock_for_update()
            self.invalidate_recordset(["historical_picking_ids"])
            if self.historical_picking_ids.filtered(lambda picking: picking.state != "cancel"):
                raise UserError(self.env._("Cancel historical preparation before changing or processing its source receipt. Completed historical consumption cannot be reused as a sale."))
        return super().write(vals)


class PosPayment(models.Model):
    _inherit = "pos.payment"

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env["pos.order"].browse(sorted({
            vals.get("pos_order_id", self.env.context.get("default_pos_order_id"))
            for vals in vals_list
        } - {None, False}))
        orders.check_access("read")
        orders.lock_for_update()
        orders.invalidate_recordset(["historical_picking_ids"])
        if orders.historical_picking_ids.filtered(lambda picking: picking.state != "cancel"):
            raise UserError(self.env._("A receipt used for historical stock consumption cannot accept a payment."))
        return super().create(vals_list)


    def write(self, vals):
        if vals.get("pos_order_id"):
            self.env["pos.order"].browse(vals["pos_order_id"])._check_no_historical_processing()
        return super().write(vals)


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    @api.model_create_multi
    def create(self, vals_list):
        originals = self.browse(sorted({vals.get("refunded_orderline_id", self.env.context.get("default_refunded_orderline_id")) for vals in vals_list} - {None, False}))
        originals.order_id._check_no_historical_processing()
        orders = self.env["pos.order"].browse(sorted({vals.get("order_id", self.env.context.get("default_order_id")) for vals in vals_list} - {None, False}))
        orders.check_access("read")
        orders.sorted("id").lock_for_update()
        if orders.historical_picking_ids.filtered(lambda picking: picking.state == "done"):
            raise UserError(self.env._("The source lines of completed historical consumption cannot be changed."))
        return super().create(vals_list)

    def write(self, vals):
        if "refunded_orderline_id" in vals:
            self.browse(vals["refunded_orderline_id"] or []).order_id._check_no_historical_processing()
        orders = self.order_id | self.env["pos.order"].browse(vals.get("order_id", []))
        orders.check_access("read")
        orders.sorted("id").lock_for_update()
        orders.invalidate_recordset(["historical_picking_ids"])
        if orders.historical_picking_ids.filtered(lambda picking: picking.state == "done"):
            raise UserError(self.env._("The source lines of completed historical consumption cannot be changed."))
        return super().write(vals)

    def unlink(self):
        self.order_id._check_no_historical_processing()
        return super().unlink()


class PosSession(models.Model):
    _inherit = "pos.session"

    historical_picking_ids = fields.One2many("stock.picking", "historical_session_id", string="Historical Stock Write-offs", copy=False)

    def action_view_historical_stock(self):
        self.check_access("read")
        self.historical_picking_ids.check_access("read")
        return {"type": "ir.actions.act_window", "name": self.env._("Historical Stock Write-offs"),
                "res_model": "stock.picking", "view_mode": "list,form",
                "domain": [("id", "in", self.historical_picking_ids.ids)]}
