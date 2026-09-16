import math
from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError

from .history import _INTERNAL, _KEY, check_permission, internal, validate_history


_LINKS = {"historical_pos_order_id", "historical_source_snapshot", "historical_applied_at", "historical_applied_by_id"}
_HISTORY = _LINKS | {"historical_session_id", "historical_effective_at", "historical_reason"}


class StockPicking(models.Model):
    _inherit = "stock.picking"

    historical_pos_order_id = fields.Many2one("pos.order", readonly=True, copy=False, check_company=True, ondelete="restrict", index=True, string="Source Receipt")
    historical_config_id = fields.Many2one(related="historical_pos_order_id.config_id")
    historical_session_id = fields.Many2one("pos.session", copy=False, check_company=True, ondelete="restrict", index=True, string="Historical Session")
    historical_effective_at = fields.Datetime(copy=False, string="Stock Operation Date", help="Effective stock date and time, independent of the linked session interval.")
    historical_reason = fields.Text(copy=False, string="Reason")
    historical_source_snapshot = fields.Char(readonly=True, copy=False)
    historical_applied_at = fields.Datetime(readonly=True, copy=False, string="Applied At")
    historical_applied_by_id = fields.Many2one("res.users", readonly=True, copy=False, string="Applied By")

    _historical_active_source = models.UniqueIndex(
        "(historical_pos_order_id) WHERE historical_pos_order_id IS NOT NULL AND state != 'cancel'",
        "Only one active historical stock document is allowed per receipt.",
    )

    @api.onchange("historical_session_id")
    def _onchange_historical_session(self):
        for picking in self:
            if not picking.historical_effective_at:
                picking.historical_effective_at = picking.historical_session_id.stop_at

    @api.model_create_multi
    def create(self, vals_list):
        supplied = set().union(*(set(vals) for vals in vals_list))
        supplied |= {key[8:] for key in self.env.context if key.startswith("default_")}
        if supplied & _HISTORY and not internal(self.env):
            raise AccessError(self.env._("Historical source links and audit data are server-managed."))
        orders = self.env["pos.order"].browse(sorted({
            vals.get("pos_order_id", self.env.context.get("default_pos_order_id")) for vals in vals_list
        } - {None, False}))
        orders._check_no_historical_processing()
        records = super().create(vals_list)
        if records.filtered("historical_pos_order_id"):
            check_permission(self.env)
        return records

    def write(self, vals):
        if vals.get("pos_order_id"):
            self.env["pos.order"].browse(vals["pos_order_id"])._check_no_historical_processing()
        if set(vals) & _LINKS and not internal(self.env):
            raise AccessError(self.env._("Historical source links and audit data are server-managed."))
        historical = self.filtered("historical_pos_order_id")
        if historical:
            check_permission(self.env)
            historical.check_access("write")
            if not internal(self.env):
                if historical.filtered(lambda picking: picking.state in ("done", "cancel")):
                    raise UserError(self.env._("Completed or cancelled historical documents cannot be edited."))
                if set(vals) & {"state", "company_id", "picking_type_id", "location_id", "location_dest_id", "pos_order_id", "pos_session_id", "date_done", "backorder_id", "return_id"}:
                    raise UserError(self.env._("Use the historical stock actions to process this document."))
            if vals.get("historical_session_id") and "historical_effective_at" not in vals:
                undated = historical.filtered(lambda picking: not picking.historical_effective_at)
                if undated:
                    undated.write(dict(vals, historical_effective_at=self.env["pos.session"].browse(vals["historical_session_id"]).stop_at))
                    return (self - undated).write(vals) if self - undated else True
            if internal(self.env) and "date_done" in vals:
                for picking in historical:
                    super(StockPicking, picking).write(dict(vals, date_done=picking.historical_effective_at))
                return super(StockPicking, self - historical).write(vals) if self - historical else True
        elif set(vals) & (_HISTORY - _LINKS):
            raise UserError(self.env._("Historical details require a document prepared from a receipt."))
        return super().write(vals)

    def copy_data(self, default=None):
        if self.filtered("historical_pos_order_id"):
            raise UserError(self.env._("Historical documents cannot be copied. Prepare them from an eligible receipt."))
        return super().copy_data(default)

    def unlink(self):
        historical = self.filtered("historical_pos_order_id")
        if historical:
            check_permission(self.env)
            if historical.filtered(lambda picking: picking.state == "done"):
                raise UserError(self.env._("Completed historical documents cannot be deleted."))
            return super(StockPicking, self.with_context(**{_KEY: _INTERNAL})).unlink()
        return super().unlink()

    def _historical_action(self):
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.act_window", "res_model": "stock.picking", "view_mode": "form", "res_id": self.id}

    def _historical_lock(self):
        self.ensure_one()
        company = self.company_id
        source = self.historical_pos_order_id
        products = self.move_ids.product_id
        for records in (company, source, self, products, products.categ_id, self.historical_session_id):
            records.check_access("read")
            records.sorted("id").lock_for_update()
            records.invalidate_recordset()
        self.env["stock.quant"].search([
            ("company_id", "=", company.id), ("product_id", "in", products.ids),
            ("location_id", "=", self.location_id.id),
        ]).sorted("id").lock_for_update()
        self.env.invalidate_all()

    def _check_historical_preparation(self):
        self.ensure_one()
        check_permission(self.env)
        self.check_access("write")
        source = self.historical_pos_order_id
        source._check_historical_source()
        if source._historical_source_snapshot() != self.historical_source_snapshot:
            raise UserError(self.env._("The source receipt changed. Cancel preparation and prepare it again."))
        session = self.historical_session_id
        session.check_access("read")
        stamp = self.historical_effective_at
        if not session or session.state != "closed" or not stamp or stamp >= fields.Datetime.now():
            raise UserError(self.env._("Select a closed session and a stock operation date in the past."))
        if (self.company_id not in self.env.companies or session.company_id != self.company_id
                or source.company_id != self.company_id or session.config_id != source.config_id
                or self.picking_type_id != source.config_id.picking_type_id
                or self.location_id != self.picking_type_id.default_location_src_id
                or self.location_id.company_id != self.company_id or self.location_dest_id.usage != "customer"
                or self.location_dest_id.company_id not in (self.env['res.company'], self.company_id)):
            raise UserError(self.env._("Historical receipt, session and stock locations must belong to the same company and POS."))
        if not (self.historical_reason or "").strip() or not self.move_ids:
            raise UserError(self.env._("Provide a reason and at least one stock line."))
        quantities = defaultdict(float)
        for move in self.move_ids:
            product = move.product_id
            quantity = move.product_uom_qty
            if (move.state != "draft" or move.company_id != self.company_id
                    or move.location_id != self.location_id or move.location_dest_id != self.location_dest_id
                    or product.company_id and product.company_id != self.company_id
                    or not product.is_storable or not math.isfinite(quantity) or quantity <= 0
                    or move.product_uom not in move.allowed_uom_ids or move.origin_returned_move_id
                    or move.move_orig_ids or move.move_dest_ids or move.route_ids):
                raise UserError(self.env._("Use positive stock quantities in the product's unit, without chained or return movements."))
            if product.tracking != "none" and not move.move_line_ids.lot_id:
                raise UserError(self.env._("A lot or serial number is required for this stock product."))
            quantities[product.id] += move.product_uom._compute_quantity(quantity, product.uom_id, round=False)
        env = self.with_company(self.company_id).with_context(allowed_company_ids=self.company_id.ids).env
        validate_history(env, self.company_id, self.move_ids.product_id.with_env(env), self.location_id, stamp, quantities)
        return quantities

    def action_apply_historical_stock(self):
        self.ensure_one()
        check_permission(self.env)
        self.check_access("write")
        if not self.historical_pos_order_id:
            raise UserError(self.env._("This is not a historical stock document."))
        with self.env.cr.savepoint():
            self._historical_lock()
            if self.state == "done":
                return self._historical_action()
            if self.state != "draft":
                raise UserError(self.env._("Only draft historical documents can be applied."))
            self._check_historical_preparation()
            picking = self.with_company(self.company_id).with_context(
                allowed_company_ids=self.company_id.ids, **{_KEY: _INTERNAL},
            )
            moves = picking.move_ids
            expected = {move.id: move.product_uom_qty for move in moves}
            picking.action_confirm()
            picking.action_assign()
            if any(move.product_uom.compare(move.quantity, expected[move.id]) for move in moves):
                raise UserError(self.env._("The complete historical quantity could not be reserved."))
            moves.picked = True
            picking._action_done()
            if (picking.state != "done" or picking.move_ids != moves or picking.backorder_ids
                    or any(move.state != "done" or move.product_uom.compare(move.quantity, expected[move.id]) for move in moves)
                    or moves.move_dest_ids or moves.account_move_id or moves.sudo().analytic_account_line_ids):
                raise UserError(self.env._("Historical stock processing did not complete without unsupported side effects."))
            picking.write({"historical_applied_at": fields.Datetime.now(), "historical_applied_by_id": self.env.user.id})
        return self._historical_action()

    def button_validate(self):
        historical = self.filtered("historical_pos_order_id")
        if historical and not internal(self.env):
            if len(self) != 1:
                raise UserError(self.env._("Apply historical documents individually."))
            return self.action_apply_historical_stock()
        return super().button_validate()

    def action_confirm(self):
        if self.filtered("historical_pos_order_id") and not internal(self.env):
            raise UserError(self.env._("Use Apply Historical Stock to confirm and complete the document."))
        return super().action_confirm()

    def action_assign(self):
        if self.filtered("historical_pos_order_id") and not internal(self.env):
            raise UserError(self.env._("Saving historical preparation must not reserve stock."))
        return super().action_assign()

    def action_cancel(self):
        historical = self.filtered("historical_pos_order_id")
        if historical:
            check_permission(self.env)
            for picking in historical.sorted("id"):
                picking._historical_lock()
            if historical.filtered(lambda picking: picking.state == "done"):
                raise UserError(self.env._("Completed historical consumption cannot be cancelled."))
            return super(StockPicking, self.with_context(**{_KEY: _INTERNAL})).action_cancel()
        return super().action_cancel()

    def action_prepare_historical_recompute(self):
        check_permission(self.env)
        self.check_access("read")
        if not self or any(not picking.historical_pos_order_id or picking.state != "done" for picking in self) or len(self.company_id) != 1:
            raise UserError(self.env._("Select completed historical documents from one company."))
        operation = self.env["pos.cost.recompute"].create({
            "company_id": self.company_id.id, "selection_type": "historical",
            "historical_picking_ids": [Command.set(self.ids)], "cost_mode": "all",
        })
        return operation._get_action()
