import math

from odoo import api, models
from odoo.exceptions import AccessError, UserError

from .history import _INTERNAL, _KEY, _VALUATION, _VALUATION_KEY, check_permission, internal


def check_audited_moves(moves):
    if moves.filtered("historical_cost_line_id"):
        raise UserError(moves.env._("Use a new reviewed historical recomputation to change an audited stock value."))


def check_stock_edit(records, pickings):
    historical = pickings.filtered("historical_pos_order_id")
    if not historical:
        return
    check_permission(records.env)
    records.check_access("write")
    if not internal(records.env) and historical.filtered(lambda picking: picking.state != "draft"):
        raise UserError(records.env._("Completed historical stock movements cannot be changed."))


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.model_create_multi
    def create(self, vals_list):
        pickings = self.env["stock.picking"].browse(sorted({
            vals.get("picking_id", self.env.context.get("default_picking_id")) for vals in vals_list
        } - {None, False}))
        check_stock_edit(self, pickings)
        return super().create(vals_list)

    def write(self, vals):
        pickings = self.picking_id | self.env["stock.picking"].browse(vals.get("picking_id", []))
        historical = self.filtered(lambda move: move.picking_id.historical_pos_order_id)
        valuation = self.env.context.get(_VALUATION_KEY) is _VALUATION
        if not (valuation and set(vals) <= {"value", "historical_cost_line_id"}):
            check_stock_edit(self, pickings)
        if pickings.filtered("historical_pos_order_id") and not internal(self.env) and not valuation:
            if set(vals) & {"state", "picking_id", "company_id", "value", "value_manual", "location_id", "location_dest_id"}:
                raise UserError(self.env._("Historical stock dimensions and values are managed by the historical actions."))
        # Before completion, date is the editable standard scheduling date.
        # Historical completion supplies the effective date through the trusted path.
        if historical and internal(self.env) and "date" in vals:
            for move in historical:
                super(StockMove, move).write(dict(vals, date=move.picking_id.historical_effective_at or vals["date"]))
            return super(StockMove, self - historical).write(vals) if self - historical else True
        return super().write(vals)

    def unlink(self):
        check_stock_edit(self, self.picking_id)
        return super().unlink()

    def copy_data(self, default=None):
        if self.picking_id.filtered("historical_pos_order_id"):
            raise UserError(self.env._("Historical stock movements cannot be copied."))
        return super().copy_data(default)

    def _action_confirm(self, merge=True, merge_into=False, create_proc=True):
        historical = self.filtered(lambda move: move.picking_id.historical_pos_order_id)
        if historical and not internal(self.env):
            raise UserError(self.env._("Use Apply Historical Stock to confirm and complete the document."))
        ordinary = super(StockMove, self - historical)._action_confirm(merge=merge, merge_into=merge_into, create_proc=create_proc)
        return ordinary | super(StockMove, historical)._action_confirm(merge=False, create_proc=create_proc) if historical else ordinary

    def _set_value(self, correction_quantity=None):
        historical = self.filtered(lambda move: move.picking_id.historical_pos_order_id)
        if historical:
            if historical.filtered(lambda move: move.state == "done"):
                raise UserError(self.env._("Use manual historical recomputation to change completed stock values."))
            if not internal(self.env):
                raise UserError(self.env._("Use Apply Historical Stock to value this document."))
            for picking, moves in historical.grouped("picking_id").items():
                super(StockMove, moves.with_context(
                    pos_historical_fifo_date=(_INTERNAL, picking.historical_effective_at),
                ))._set_value(correction_quantity=correction_quantity)
        return super(StockMove, self - historical)._set_value(correction_quantity=correction_quantity)

    def _check_historical_purchase_valuation(self):
        """Validate historical facts after the caller locks its complete cost plan."""
        check_permission(self.env)
        self.check_access("read")
        self.check_access("write")
        company = self.env.company
        if self.env.companies != company or self.company_id != company:
            raise AccessError(self.env._("Historical purchase valuation requires one current allowed company."))
        pickings = self.picking_id
        sources = pickings.historical_pos_order_id
        sessions = pickings.historical_session_id | sources.session_id
        for records in (pickings, self.move_line_ids, sources, sources.lines, sessions,
                        self.product_id, self.location_id | self.location_dest_id):
            records.check_access("read")
        sources._check_historical_source()
        if self.filtered(lambda move: move.cost_repair_line_id or move.historical_cost_line_id):
            raise UserError(self.env._("Historical purchase valuation cannot replace a protected previous cost correction."))
        for move in self:
            picking = move.picking_id
            source = picking.historical_pos_order_id
            session = picking.historical_session_id
            if (not source or not session or move.state != "done" or picking.state != "done"
                    or picking.company_id != company or source.company_id != company
                    or source.session_id.company_id != company or session.company_id != company
                    or source.state not in ("draft", "cancel") or session.state != "closed"
                    or session.config_id != source.config_id or picking.pos_order_id or picking.pos_session_id
                    or not picking.historical_applied_at or not picking.historical_source_snapshot
                    or not picking.historical_effective_at or move.date != picking.historical_effective_at
                    or picking.date_done != picking.historical_effective_at):
                raise UserError(self.env._("Historical purchase valuation requires a completed historical write-off and its unchanged source links."))
            product = move.product_id
            quantity = move._get_valued_qty()
            lines = move.move_line_ids
            if (product.type != "consu" or product.tracking != "none" or product.lot_valuated
                    or product.company_id and product.company_id != company
                    or product.cost_method != "fifo" or product.valuation != "periodic"
                    or not move.is_out or move.is_in or move.is_dropship or move.origin_returned_move_id
                    or move.move_orig_ids or move.move_dest_ids or move.route_ids
                    or move.location_id != picking.location_id or move.location_dest_id != picking.location_dest_id
                    or move.location_id.usage != "internal" or not move.location_id.is_valued_internal
                    or move.location_id.company_id != company or move.location_dest_id.usage != "customer"
                    or move.location_dest_id.company_id not in (self.env["res.company"], company)
                    or move.product_uom != product.uom_id or not math.isfinite(quantity) or quantity <= 0
                    or not math.isfinite(move.quantity) or product.uom_id.compare(move.quantity, quantity)
                    or not lines or lines.filtered(lambda line:
                        line.product_id != product or line.product_uom_id != product.uom_id
                        or line.company_id != company or line.date != move.date
                        or line.location_id != move.location_id or line.location_dest_id != move.location_dest_id
                        or line.owner_id or line.lot_id or line.package_id or line.result_package_id
                        or not line.picked or not math.isfinite(line.quantity) or line.quantity <= 0
                    ) or product.uom_id.compare(sum(lines.mapped("quantity")), quantity)):
                raise UserError(self.env._("Historical purchase valuation requires consistent untracked outgoing stock quantities and locations."))
        return True

    def _write_historical_purchase_values(self, values_by_move_id):
        """Keep the valuation capability local to the exact validated movements."""
        self._check_historical_purchase_valuation()
        if (not isinstance(values_by_move_id, dict) or set(values_by_move_id) != set(self.ids)
                or any(isinstance(value, bool) or not isinstance(value, (int, float))
                       or not math.isfinite(value) or value <= 0 for value in values_by_move_id.values())):
            raise UserError(self.env._("Provide one finite positive historical value for each validated movement."))
        context = {
            "lang": self.env.lang,
            "tz": self.env.context.get("tz"),
            "allowed_company_ids": self.env.company.ids,
            _VALUATION_KEY: _VALUATION,
        }
        for move in self:
            move.with_context(context).write({"value": values_by_move_id[move.id]})
        return True


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        moves = self.env["stock.move"].browse(sorted({
            vals.get("move_id", self.env.context.get("default_move_id")) for vals in vals_list
        } - {None, False}))
        pickings = moves.picking_id | self.env["stock.picking"].browse(sorted({
            vals.get("picking_id", self.env.context.get("default_picking_id")) for vals in vals_list
        } - {None, False}))
        check_audited_moves(moves)
        check_stock_edit(self, pickings)
        return super().create(vals_list)

    def write(self, vals):
        moves = self.move_id | self.env["stock.move"].browse(vals.get("move_id", []))
        check_audited_moves(moves)
        pickings = self.picking_id | moves.picking_id | self.env["stock.picking"].browse(vals.get("picking_id", []))
        check_stock_edit(self, pickings)
        historical = self.filtered(lambda line: line.move_id.picking_id.historical_pos_order_id)
        if pickings.filtered("historical_pos_order_id") and not internal(self.env) and set(vals) & {"move_id", "picking_id", "state", "date", "company_id", "location_id", "location_dest_id"}:
            raise UserError(self.env._("Historical stock dimensions and values are managed by the historical actions."))
        if historical and internal(self.env) and "date" in vals:
            for line in historical:
                super(StockMoveLine, line).write(dict(vals, date=line.move_id.picking_id.historical_effective_at or vals["date"]))
            return super(StockMoveLine, self - historical).write(vals) if self - historical else True
        return super().write(vals)

    def unlink(self):
        check_audited_moves(self.move_id)
        check_stock_edit(self, self.picking_id | self.move_id.picking_id)
        return super().unlink()


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _run_fifo(self, quantity, lot=None, at_date=None, location=None):
        value = self.env.context.get("pos_historical_fifo_date")
        if isinstance(value, tuple) and len(value) == 2 and value[0] is _INTERNAL:
            at_date = value[1]
        return super()._run_fifo(quantity, lot=lot, at_date=at_date, location=location)


class ProductValue(models.Model):
    _inherit = "product.value"

    @api.model_create_multi
    def create(self, vals_list):
        moves = self.env["stock.move"].browse(sorted({
            vals.get("move_id", self.env.context.get("default_move_id")) for vals in vals_list
        } - {None, False}))
        check_audited_moves(moves)
        check_stock_edit(self, moves.picking_id)
        return super().create(vals_list)

    def write(self, vals):
        moves = self.move_id | self.env["stock.move"].browse(vals.get("move_id", []))
        check_audited_moves(moves)
        check_stock_edit(self, moves.picking_id)
        return super().write(vals)

    def unlink(self):
        check_audited_moves(self.move_id)
        check_stock_edit(self, self.move_id.picking_id)
        return super().unlink()
