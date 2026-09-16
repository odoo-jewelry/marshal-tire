from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare

from odoo.addons.pos_cost_recompute.models.pos_cost_recompute import _CONTEXT_KEY, _INTERNAL as COST_INTERNAL

from .history import (
    _VALUATION, _VALUATION_KEY, check_permission, check_period, digest, fifo_values,
    read_history, validate_history,
)


class PosCostRecompute(models.Model):
    _inherit = "pos.cost.recompute"

    selection_type = fields.Selection(selection_add=[("historical", "Historical Stock Write-offs"), ("consolidation", "Consolidated Product History")], ondelete={"historical": "set default", "consolidation": "set default"})
    consolidation_operation_ids = fields.Many2many("product.consolidation.operation", check_company=True, string="History Consolidations")
    history_start_at = fields.Datetime(readonly=True, copy=False, string="Recompute From")
    historical_picking_ids = fields.Many2many("stock.picking", check_company=True, string="Historical Stock Write-offs")
    historical_cutoff = fields.Datetime(readonly=True, copy=False, string="History Through")
    historical_evidence = fields.Char(readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        prepared = []
        for vals in vals_list:
            vals = dict(vals)
            historical = vals.get("selection_type", self.env.context.get("default_selection_type")) in ("historical", "consolidation")
            if historical or vals.get("consolidation_operation_ids") or vals.get("historical_picking_ids") or self.env.context.get("default_historical_picking_ids"):
                check_permission(self.env)
            if historical:
                vals.setdefault("cost_mode", "all")
            prepared.append(vals)
        return super().create(prepared)

    def write(self, vals):
        if (vals.get("selection_type") in ("historical", "consolidation") or vals.get("historical_picking_ids") or vals.get("consolidation_operation_ids")
                or self.filtered(lambda operation: operation.selection_type in ("historical", "consolidation"))):
            check_permission(self.env)
        return super().write(vals)

    @api.onchange("selection_type")
    def _onchange_historical_selection(self):
        if self.selection_type in ("historical", "consolidation"):
            self.cost_mode = "all"
            self.product_ids = False
            self.config_ids = False
            self.repair_stock_values = False

    @api.model
    def _selection_fields(self):
        return super()._selection_fields() | {"historical_picking_ids", "consolidation_operation_ids"}

    @api.depends("selection_type", "stock_line_ids", "state", "line_ids.status", "line_ids.old_cost", "line_ids.new_cost", "line_ids.currency_id", "line_ids.zero_source")
    def _compute_summary(self):
        super()._compute_summary()
        for operation in self.filtered(lambda item: item.selection_type in ("historical", "consolidation")):
            operation.can_apply = operation.state == "ready" and bool(operation.stock_line_ids)

    def copy_data(self, default=None):
        values = super().copy_data(default)
        for operation, vals in zip(self, values):
            if operation.selection_type in ("historical", "consolidation"):
                vals["historical_picking_ids"] = [Command.set(operation.historical_picking_ids.ids)]
                vals["consolidation_operation_ids"] = [Command.set(operation.consolidation_operation_ids.ids)]
        return values

    def _history_selection(self):
        self.ensure_one()
        if self.cost_mode != "all" or self.product_ids or self.config_ids or self.repair_stock_values:
            raise UserError(self.env._("History recomputation requires all matching costs without ordinary filters or stock repair."))
        if self.selection_type == "consolidation":
            operations = self.consolidation_operation_ids
            operations.check_access("read")
            if not operations or operations.company_id != self.company_id or self.historical_picking_ids:
                raise UserError(self.env._("Select applied full-history consolidations from one company."))
            templates = operations.canonical_id
            if any(not template._has_full_consolidation_history(self.company_id) for template in templates):
                raise UserError(self.env._("Convert all remaining source histories before recomputation."))
            products = templates.with_context(active_test=False).product_variant_ids
            moves = read_history(self.env, self.company_id, products).filtered(lambda move: move.state == "done")
            outgoing = moves.filtered("is_out")
            if outgoing and len(outgoing.location_id) != 1:
                raise UserError(self.env._("A supported history with outgoing movements in one stock location is required."))
            location = outgoing.location_id or moves.location_dest_id.filtered(lambda item: item.usage == "internal")
            start = min(outgoing.mapped("date"), default=self.historical_cutoff or fields.Datetime.now())
        else:
            picks = self.historical_picking_ids
            picks.check_access("read")
            if (not picks or picks.company_id != self.company_id or self.consolidation_operation_ids
                    or any(not picking.historical_pos_order_id or picking.state != "done" for picking in picks)
                    or len(picks.location_id) != 1):
                raise UserError(self.env._("Select completed historical stock documents from one company and stock location."))
            products, location = picks.move_ids.product_id, picks.location_id
            start = min(picks.mapped("historical_effective_at"))
            for template in products.product_tmpl_id:
                if template._has_full_consolidation_history(self.company_id):
                    boundaries = template._full_history_operations(self.company_id).mapped("earliest_issue_at")
                    start = min([start] + [date for date in boundaries if date])
        return products, location, start

    def _historical_plan(self):
        self.ensure_one()
        check_permission(self.env)
        self._check_manager()
        products, location, start = self._history_selection()
        cutoff = self.historical_cutoff or fields.Datetime.now()
        operation = self.with_company(self.company_id).with_context(allowed_company_ids=self.company_id.ids)
        if self.selection_type == "consolidation" and not location:
            history = read_history(operation.env, operation.company_id, products)
            if not history.filtered(lambda move: move.state == "done"):
                return history, self.env["stock.move"], {}
        history = validate_history(operation.env, operation.company_id, products.with_env(operation.env), location, start)
        issues = history.filtered(lambda move: move.state == "done" and move.is_out and start <= move.date <= cutoff)
        for timestamp in set(issues.mapped("date")):
            check_period(operation.env, operation.company_id, timestamp)
        return history, issues, fifo_values(issues)

    def _select_lines(self):
        if self.selection_type not in ("historical", "consolidation"):
            return super()._select_lines()
        _history, issues, _values = self._historical_plan()
        picks = issues.picking_id.filtered(lambda picking: not picking.historical_pos_order_id)
        orders = (picks.pos_order_id | picks.pos_session_id.order_ids).filtered(lambda order: order.state in ("paid", "done", "invoiced"))
        orders.check_access("read")
        lines = orders.lines.filtered(lambda line: line.product_id in issues.product_id)
        lines.check_access("read")
        return lines

    def _prepare_proposals(self, selected, lang):
        proposals = super()._prepare_proposals(selected, lang)
        if self.selection_type not in ("historical", "consolidation"):
            return proposals
        history, _issues, values = self._historical_plan()
        evidence = digest(history)
        digits = self.env["decimal.precision"].precision_get("Product Price")
        for proposal in proposals:
            if proposal["skip_reason"]:
                raise UserError(self.env._("Historical recomputation cannot include this POS source: %(reason)s", reason=proposal["skip_reason"]))
            line = selected.browse(proposal["pos_line_id"])
            moves = self.env["stock.move"].browse(proposal["move_ids"][0][2]).filtered(lambda move: move.state == "done")
            quantity = sum(move._get_valued_qty() for move in moves)
            if not quantity:
                raise UserError(self.env._("A complete stock source is required for historical POS cost recomputation."))
            unit = sum(values.get(move.id, move.value) for move in moves) / quantity
            new_cost = line.qty * line.product_id.cost_currency_id._convert(
                unit, line.currency_id, self.company_id, line.order_id.date_order, round=False,
            )
            status = "changed" if float_compare(line.total_cost, new_cost, precision_digits=digits) else (
                "unchanged" if line.is_total_cost_computed else "completion"
            )
            proposal.update(new_cost=new_cost, new_computed=True, zero_source=False, status=status)
            proposal["snapshot"].update(historical_evidence=evidence, historical_cost=new_cost)
        return proposals

    def action_preview(self):
        if self.selection_type not in ("historical", "consolidation"):
            return super().action_preview()
        check_permission(self.env)
        self.check_access("write")
        with self.env.cr.savepoint():
            self._internal_write({"historical_cutoff": fields.Datetime.now(), "history_start_at": self._history_selection()[2]})
            result = super().action_preview()
            history, issues, values = self._historical_plan()
            self.env["pos.cost.recompute.stock.line"].with_context(**{_CONTEXT_KEY: COST_INTERNAL}).create([{
                "operation_id": self.id, "move_id": move.id, "company_id": self.company_id.id,
                "currency_id": self.company_id.currency_id.id, "product_id": move.product_id.id,
                "quantity": move._get_valued_qty(), "old_value": move.value, "new_value": values[move.id],
                "status": "repair", "snapshot": {"date": str(move.date)},
            } for move in issues])
            self._internal_write({"historical_evidence": digest(history)})
        return result

    def _lock_sources(self, selected):
        if self.selection_type in ("historical", "consolidation"):
            check_permission(self.env)
            picks = self.historical_picking_ids
            products = self._history_selection()[0]
            for records in (self.company_id, products, products.categ_id, picks, picks.historical_pos_order_id, self.consolidation_operation_ids):
                records.check_access("read")
                records.sorted("id").lock_for_update()
                records.invalidate_recordset()
            history = read_history(self.env, self.company_id, products)
            for records in (history, history.move_line_ids):
                records.sorted("id").lock_for_update()
                records.invalidate_recordset()
        return super()._lock_sources(selected)

    def _apply_stock_plan(self):
        super()._apply_stock_plan()
        if self.selection_type not in ("historical", "consolidation"):
            return
        history, issues, values = self._historical_plan()
        if (digest(history) != self.historical_evidence or issues != self.stock_line_ids.move_id.sorted(lambda move: (move.date, move.id))
                or any(line.new_value != values.get(line.move_id.id) for line in self.stock_line_ids)):
            raise UserError(self.env._("The historical preview is stale. Review current history before applying."))
        for line in self.stock_line_ids:
            line.move_id.check_access("write")
            line.move_id.with_context(**{_VALUATION_KEY: _VALUATION}).write({
                "value": line.new_value, "historical_cost_line_id": line.id,
            })
            line.with_context(**{_CONTEXT_KEY: COST_INTERNAL}).write({"actual_value": line.move_id.value})


class StockMove(models.Model):
    _inherit = "stock.move"

    historical_cost_line_id = fields.Many2one("pos.cost.recompute.stock.line", readonly=True, copy=False, ondelete="restrict", check_company=True, string="Historical Cost Recalculation")

    @api.model_create_multi
    def create(self, vals_list):
        if any("historical_cost_line_id" in vals for vals in vals_list) or self.env.context.get("default_historical_cost_line_id"):
            raise AccessError(self.env._("Historical cost audit links are server-managed."))
        return super().create(vals_list)

    def write(self, vals):
        allowed = self.env.context.get(_VALUATION_KEY) is _VALUATION
        if "historical_cost_line_id" in vals and not allowed:
            raise AccessError(self.env._("Historical cost audit links are server-managed."))
        if self.filtered("historical_cost_line_id") and not allowed and set(vals) & {
            "value", "value_manual", "quantity", "product_uom_qty", "product_id", "product_uom",
            "state", "date", "location_id", "location_dest_id", "company_id", "picking_id", "move_line_ids",
        }:
            raise UserError(self.env._("Use a new reviewed historical recomputation to change an audited stock value."))
        return super().write(vals)

    def _set_value(self, correction_quantity=None):
        audited = self.filtered("historical_cost_line_id")
        if audited:
            raise UserError(self.env._("Use a new reviewed historical recomputation to change an audited stock value."))
        return super()._set_value(correction_quantity=correction_quantity)

    def unlink(self):
        if self.filtered("historical_cost_line_id"):
            raise UserError(self.env._("Audited historical stock values cannot be deleted."))
        return super().unlink()


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    def _check_historical_stock_removal(self):
        if "pos_historical_stock_writeoff" in self.mapped("name") and self.env["stock.picking"].sudo().search_count([
            ("historical_pos_order_id", "!=", False), ("state", "=", "done"),
        ], limit=1):
            # Uninstallation is global: retain audit protection in every company.
            raise UserError(self.env._("Historical Stock Write-off cannot be removed while completed historical documents exist."))

    def write(self, vals):
        if vals.get("state") == "to remove":
            self._check_historical_stock_removal()
        return super().write(vals)

    def button_uninstall(self):
        (self | self.downstream_dependencies())._check_historical_stock_removal()
        return super().button_uninstall()

    def module_uninstall(self):
        self._check_historical_stock_removal()
        return super().module_uninstall()
