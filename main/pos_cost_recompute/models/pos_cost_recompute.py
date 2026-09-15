from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, format_amount


_INTERNAL = object()
_CONTEXT_KEY = "pos_cost_recompute_internal"
_CRITERIA = {
    "company_id", "selection_type", "order_ids", "date_from", "date_to",
    "config_ids", "product_ids", "cost_mode", "repair_stock_values",
}
_EDITABLE = _CRITERIA | {"reason", "allow_zero_cost", "acknowledge_stock_repair"}


class PosCostRecompute(models.Model):
    _name = "pos.cost.recompute"
    _description = "POS Cost Recomputation"
    _order = "id desc"
    _check_company_auto = True

    name = fields.Char(compute="_compute_name")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )
    selection_type = fields.Selection(
        [("orders", "Selected Orders"), ("period", "Date Interval")],
        required=True, default="period",
    )
    order_ids = fields.Many2many("pos.order", check_company=True, string="Orders")
    date_from = fields.Datetime(string="From (inclusive)")
    date_to = fields.Datetime(string="To (exclusive)")
    config_ids = fields.Many2many("pos.config", check_company=True, string="Point of Sale")
    product_ids = fields.Many2many("product.product", check_company=True, string="Products")
    cost_mode = fields.Selection(
        [("zero", "Zero Saved Costs Only"), ("all", "All Matching Lines")],
        required=True, default="zero",
    )
    reason = fields.Text(string="Reason")
    allow_zero_cost = fields.Boolean(string="I acknowledge zero source costs")
    state = fields.Selection(
        [("draft", "Draft"), ("ready", "Reviewed"), ("done", "Applied"),
         ("cancelled", "Cancelled")],
        required=True, default="draft", readonly=True, copy=False,
    )
    line_ids = fields.One2many(
        "pos.cost.recompute.line", "operation_id", readonly=True, copy=False,
    )
    applied_by_id = fields.Many2one("res.users", readonly=True, copy=False)
    applied_at = fields.Datetime(readonly=True, copy=False)
    preview_lang = fields.Char(readonly=True, copy=False)
    changed_count = fields.Integer(compute="_compute_summary")
    unchanged_count = fields.Integer(compute="_compute_summary")
    completion_count = fields.Integer(compute="_compute_summary")
    skipped_count = fields.Integer(compute="_compute_summary")
    zero_count = fields.Integer(compute="_compute_summary")
    can_apply = fields.Boolean(compute="_compute_summary")
    summary = fields.Text(compute="_compute_summary")
    incomplete_order_ids = fields.Many2many(
        "pos.order", compute="_compute_summary", string="Orders with incomplete costs",
    )

    @api.depends("state")
    def _compute_name(self):
        for operation in self:
            operation.name = self.env._("Cost recomputation #%(id)s", id=operation.id or "")

    @api.depends("state", "line_ids.status", "line_ids.zero_source",
                 "line_ids.old_cost", "line_ids.new_cost", "line_ids.currency_id")
    def _compute_summary(self):
        for operation in self:
            for status, field in (("changed", "changed_count"), ("unchanged", "unchanged_count"),
                                  ("completion", "completion_count"), ("skipped", "skipped_count")):
                operation[field] = len(operation.line_ids.filtered(lambda line: line.status == status))
            eligible = operation.line_ids.filtered(lambda line: line.status != "skipped")
            operation.zero_count = len(eligible.filtered("zero_source"))
            operation.can_apply = operation.state == "ready" and bool(eligible)
            amounts = []
            for currency, lines in eligible.grouped("currency_id").items():
                old = sum(lines.mapped("old_cost"))
                new = sum(lines.mapped("new_cost"))
                amounts.append(self.env._(
                    "%(currency)s: previous cost %(old)s; proposed cost %(new)s; margin change %(delta)s",
                    currency=currency.name, old=format_amount(self.env, old, currency),
                    new=format_amount(self.env, new, currency),
                    delta=format_amount(self.env, old - new, currency),
                ))
            operation.summary = "\n".join(amounts)
            completed_lines = eligible.pos_line_id
            operation.incomplete_order_ids = operation.line_ids.pos_line_id.order_id.filtered(
                lambda order: bool((order.lines - completed_lines).filtered(
                    lambda line: not line.is_total_cost_computed
                ))
            )

    def _check_manager(self):
        if not self.env.user.has_group("point_of_sale.group_pos_manager"):
            raise AccessError(self.env._("Only POS managers can recompute costs."))
        self.check_access("read")
        if any(company not in self.env.companies for company in self.company_id):
            raise AccessError(self.env._("The operation company is not allowed."))

    @api.constrains("company_id", "order_ids", "config_ids", "product_ids")
    def _check_selection_company(self):
        self._check_manager()
        for operation in self:
            for records in (operation.order_ids, operation.config_ids, operation.product_ids):
                records.check_access("read")
                if any(company != operation.company_id for company in records.company_id):
                    raise UserError(self.env._("All selected records must belong to the operation company."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_manager()
        if any(set(vals) - _EDITABLE for vals in vals_list):
            raise AccessError(self.env._("Only selection criteria and confirmation inputs can be supplied."))
        # RPC context defaults must not forge server-owned state or history.
        context = {key: value for key, value in self.env.context.items()
                   if not key.startswith("default_") or key[8:] in _EDITABLE}
        return super(PosCostRecompute, self.with_context(context)).create(vals_list)

    def write(self, vals):
        self._check_manager()
        if self.env.context.get(_CONTEXT_KEY) is not _INTERNAL:
            if self.filtered(lambda operation: operation.state in ("done", "cancelled")):
                raise UserError(self.env._("Applied or cancelled operations cannot be edited."))
            if set(vals) - _EDITABLE:
                raise AccessError(self.env._("Preview results and history are server-managed."))
            if set(vals) & _CRITERIA:
                self._internal_write({"state": "draft", "allow_zero_cost": False})
                self._clear_preview()
        return super().write(vals)

    def unlink(self):
        self._check_manager()
        if self.filtered(lambda operation: operation.state != "draft"):
            raise UserError(self.env._("Only draft operations can be deleted."))
        self._clear_preview()
        return super().unlink()

    def copy_data(self, default=None):
        self._check_manager()
        values = []
        for operation in self:
            vals = {
                "company_id": operation.company_id.id,
                "selection_type": operation.selection_type,
                "order_ids": [Command.set(operation.order_ids.ids)],
                "date_from": operation.date_from,
                "date_to": operation.date_to,
                "config_ids": [Command.set(operation.config_ids.ids)],
                "product_ids": [Command.set(operation.product_ids.ids)],
                "cost_mode": operation.cost_mode,
                "repair_stock_values": operation.repair_stock_values,
            }
            vals.update(default or {})
            values.append(vals)
        return values

    def action_preview(self):
        self.ensure_one()
        self._check_manager()
        self.check_access("write")
        self.lock_for_update()
        if self.state not in ("draft", "ready"):
            raise UserError(self.env._("Only draft or reviewed operations can be previewed."))
        with self.env.cr.savepoint():
            selected = self._select_lines()
            proposals = self._prepare_proposals(selected, lang=self.env.lang)
            self._clear_preview()
            self.env["pos.cost.recompute.line"].with_context(**{_CONTEXT_KEY: _INTERNAL}).create([
                dict(values, operation_id=self.id) for values in proposals
            ])
            self._internal_write({"state": "ready", "allow_zero_cost": False,
                                  "preview_lang": self.env.lang})
        return self._get_action()

    def action_apply(self):
        self.ensure_one()
        self._check_manager()
        self.check_access("write")
        with self.env.cr.savepoint():
            self.lock_for_update()
            self.invalidate_recordset()
            if self.state == "done":
                return self._get_action()
            if not self.can_apply:
                raise UserError(self.env._("Prepare a current preview containing eligible lines first."))
            if not (self.reason or "").strip():
                raise UserError(self.env._("A reason is required before applying cost changes."))
            if self.zero_count and not self.allow_zero_cost:
                raise UserError(self.env._(
                    "Acknowledge the zero source costs. Recomputing cannot repair a zero source."
                ))
            selected = self.line_ids.pos_line_id
            selected.check_access("read")
            selected.check_access("write")
            selected.order_id.check_access("read")
            selected.order_id.check_access("write")
            self._lock_sources(selected)
            proposals = self._prepare_proposals(selected, lang=self.preview_lang)
            old_by_id = {line.pos_line_id.id: line for line in self.line_ids}
            if len(proposals) != len(old_by_id) or any(
                proposal["snapshot"] != old_by_id[proposal["pos_line_id"]].snapshot
                for proposal in proposals
            ):
                raise UserError(self.env._("The preview is stale. Review current data before applying."))
            self._apply_stock_plan()
            groups = defaultdict(lambda: self.env["pos.order.line"])
            for detail in self.line_ids.filtered(lambda line: line.status in ("changed", "completion")):
                groups[tuple(sorted(detail.move_ids.ids))] |= detail.pos_line_id
            digits = self.env["decimal.precision"].precision_get("Product Price")
            for move_ids, lines in groups.items():
                lines = lines.with_company(self.company_id)
                lines.write({"is_total_cost_computed": False})
                lines._compute_total_cost(self.env["stock.move"].browse(move_ids))
                for line in lines:
                    if not line.is_total_cost_computed or float_compare(
                        line.total_cost, old_by_id[line.id].new_cost, precision_digits=digits
                    ):
                        raise UserError(self.env._("Standard calculation differs from the reviewed proposal."))
            for detail in self.line_ids:
                detail.with_context(**{_CONTEXT_KEY: _INTERNAL}).write({
                    "actual_cost": detail.pos_line_id.total_cost,
                    "actual_computed": detail.pos_line_id.is_total_cost_computed,
                })
            self._internal_write({"state": "done", "applied_by_id": self.env.user.id,
                                  "applied_at": fields.Datetime.now()})
        return self._get_action()

    def action_cancel(self):
        self._check_manager()
        self.check_access("write")
        self.lock_for_update()
        if self.filtered(lambda operation: operation.state not in ("draft", "ready")):
            raise UserError(self.env._("Only unapplied operations can be cancelled."))
        self._internal_write({"state": "cancelled"})
        return True

    def _internal_write(self, values):
        return self.with_context(**{_CONTEXT_KEY: _INTERNAL}).write(values)

    def _clear_preview(self):
        self.line_ids.with_context(**{_CONTEXT_KEY: _INTERNAL}).unlink()

    def _apply_stock_plan(self):
        """Extension point after snapshot validation, inside the apply savepoint."""

    def _get_action(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "res_model": self._name,
            "view_mode": "form", "res_id": self.id, "target": "current",
        }

    def _select_lines(self):
        self.ensure_one()
        self._check_selection_company()
        domain = [("company_id", "=", self.company_id.id)]
        if self.selection_type == "orders":
            if not self.order_ids:
                raise UserError(self.env._("Select at least one order."))
            domain.append(("order_id", "in", self.order_ids.ids))
        else:
            if not self.date_from or not self.date_to or self.date_from >= self.date_to:
                raise UserError(self.env._("Provide a valid bounded date interval."))
            domain.extend([("order_id.date_order", ">=", self.date_from),
                           ("order_id.date_order", "<", self.date_to)])
        if self.config_ids:
            domain.append(("order_id.config_id", "in", self.config_ids.ids))
        if self.product_ids:
            domain.append(("product_id", "in", self.product_ids.ids))
        if self.cost_mode == "zero":
            digits = self.env["decimal.precision"].precision_get("Product Price")
            threshold = 0.5 * 10 ** -digits
            domain.extend([("total_cost", ">", -threshold), ("total_cost", "<", threshold)])
        return self.env["pos.order.line"].with_context(active_test=False).search(
            domain, order="id"
        )

    def _prepare_proposals(self, selected, lang):
        selected = selected.with_company(self.company_id).with_context(active_test=False, lang=lang)
        if any(company != self.company_id for company in selected.company_id):
            raise AccessError(self.env._("Selected lines must belong to the operation company."))
        return [line._prepare_cost_recompute_proposal(selected) for line in selected]

    def _lock_sources(self, selected):
        move_ids = {item[0] for detail in self.line_ids for item in detail.snapshot["moves"]}
        moves = self.env["stock.move"].browse(sorted(move_ids))
        sources = [
            selected.order_id.session_id, selected.order_id, selected,
            selected.product_id.product_tmpl_id, selected.product_id,
            selected.product_id.categ_id, selected.product_id.uom_id,
            moves.picking_id, moves, moves.move_line_ids,
        ]
        for records in sources:
            records.check_access("read")
            records.sorted("id").lock_for_update()
            records.invalidate_recordset()


class PosCostRecomputeLine(models.Model):
    _name = "pos.cost.recompute.line"
    _description = "POS Cost Recomputation Detail"
    _order = "id"
    _check_company_auto = True

    operation_id = fields.Many2one("pos.cost.recompute", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one("res.company", required=True)
    pos_line_id = fields.Many2one("pos.order.line", required=True, ondelete="restrict", check_company=True)
    order_id = fields.Many2one(related="pos_line_id.order_id")
    product_id = fields.Many2one("product.product", required=True, ondelete="restrict", check_company=True)
    currency_id = fields.Many2one("res.currency", required=True)
    quantity = fields.Float(readonly=True)
    old_cost = fields.Float(readonly=True, min_display_digits="Product Price")
    new_cost = fields.Float(readonly=True, min_display_digits="Product Price")
    actual_cost = fields.Float(readonly=True, min_display_digits="Product Price")
    old_computed = fields.Boolean(readonly=True)
    new_computed = fields.Boolean(readonly=True)
    actual_computed = fields.Boolean(readonly=True)
    margin_delta = fields.Float(compute="_compute_margin_delta")
    source = fields.Selection(
        [("product", "Current Company Product Cost"), ("order_moves", "Order Stock Valuation"),
         ("session_moves", "Weighted Product Cost across the Session")], readonly=True,
    )
    status = fields.Selection(
        [("changed", "Cost Change"), ("unchanged", "Unchanged"),
         ("completion", "Completion Marker Only"), ("skipped", "Skipped")],
        required=True, readonly=True,
    )
    skip_reason = fields.Text(readonly=True)
    zero_source = fields.Boolean(readonly=True, string="Zero source acknowledgement required")
    snapshot = fields.Json(readonly=True)
    move_ids = fields.Many2many("stock.move", readonly=True, check_company=True)
    related_line_ids = fields.Many2many("pos.order.line", readonly=True, check_company=True,
                                      string="Related lines outside selection")

    @api.depends("status", "old_cost", "new_cost")
    def _compute_margin_delta(self):
        for line in self:
            line.margin_delta = line.old_cost - line.new_cost if line.status != "skipped" else 0

    def _check_internal(self):
        self.env["pos.cost.recompute"]._check_manager()
        if self.env.context.get(_CONTEXT_KEY) is not _INTERNAL:
            raise AccessError(self.env._("Recomputation details are server-managed and cannot be edited."))

    @api.model_create_multi
    def create(self, vals_list):
        self._check_internal()
        return super().create(vals_list)

    def write(self, vals):
        self._check_internal()
        return super().write(vals)

    def unlink(self):
        self._check_internal()
        if self.operation_id.filtered(lambda operation: operation.state in ("done", "cancelled")):
            raise UserError(self.env._("Applied or cancelled history cannot be deleted."))
        return super().unlink()
