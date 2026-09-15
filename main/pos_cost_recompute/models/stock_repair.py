import hashlib
import json
import math
from datetime import date, datetime

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_compare, format_amount

from .pos_cost_recompute import _CONTEXT_KEY, _INTERNAL
from .source_revision import _touch


_MOVE_FIELDS = [
    "state", "company_id", "product_id", "product_uom", "quantity", "date", "value",
    "location_id", "location_dest_id", "picked", "origin_returned_move_id", "picking_id",
    "account_move_id", "cost_repair_line_id",
]
_ML_FIELDS = ["move_id", "product_id", "company_id", "product_uom_id", "quantity", "picked",
              "location_id", "location_dest_id", "owner_id", "lot_id"]


def _json_value(value):
    if isinstance(value, (datetime, date)):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


class PosCostRecompute(models.Model):
    _inherit = "pos.cost.recompute"

    repair_stock_values = fields.Boolean(
        string="Repair Zero Stock Values and Recompute POS", default=False,
    )
    acknowledge_stock_repair = fields.Boolean(
        string="I acknowledge changes to historical stock values", copy=False,
    )
    stock_line_ids = fields.One2many(
        "pos.cost.recompute.stock.line", "operation_id", readonly=True, copy=False,
    )
    stock_repair_count = fields.Integer(compute="_compute_stock_summary")
    stock_summary = fields.Text(compute="_compute_stock_summary")
    stock_evidence = fields.Json(readonly=True, copy=False)

    @api.depends("stock_line_ids.status", "stock_line_ids.old_value", "stock_line_ids.new_value",
                 "stock_line_ids.currency_id")
    def _compute_stock_summary(self):
        for operation in self:
            lines = operation.stock_line_ids.filtered(lambda line: line.status == "repair")
            operation.stock_repair_count = len(lines)
            operation.stock_summary = "\n".join(self.env._(
                "Stock value: %(old)s → %(new)s",
                old=format_amount(self.env, sum(group.mapped("old_value")), currency),
                new=format_amount(self.env, sum(group.mapped("new_value")), currency),
            ) for currency, group in lines.grouped("currency_id").items())

    def _check_manager(self):
        super()._check_manager()
        if self.filtered("repair_stock_values") and not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(self.env._("Stock repair requires POS-manager and stock-manager permissions."))

    @api.constrains("repair_stock_values")
    def _check_stock_repair_permission(self):
        self._check_manager()

    def _clear_preview(self):
        super()._clear_preview()
        if self.stock_line_ids:
            self.stock_line_ids.with_context(**{_CONTEXT_KEY: _INTERNAL}).unlink()
        self._internal_write({"acknowledge_stock_repair": False, "stock_evidence": False})

    def action_preview(self):
        with self.env.cr.savepoint():
            result = super().action_preview()
            if self.repair_stock_values:
                operation = self.with_company(self.company_id).with_context(lang=self.preview_lang, active_test=False)
                selected = self.line_ids.pos_line_id.with_env(operation.env)
                _, plans = operation._prepare_stock_proposals(
                    selected, super(PosCostRecompute, operation)._prepare_proposals(selected, self.preview_lang),
                    return_plans=True,
                )
                details = self.env["pos.cost.recompute.stock.line"].with_context(
                    **{_CONTEXT_KEY: _INTERNAL}
                ).create([dict(plan, operation_id=self.id) for plan in plans.values()])
                history = self._read_stock_history(details.product_id)
                self._internal_write({"stock_evidence": {
                    str(product.id): self._stock_history_snapshot(moves)
                    for product, moves in history.grouped("product_id").items()
                }})
                for detail in self.line_ids:
                    ids = {plan[0] for plan in detail.snapshot.get("stock_plan", [])}
                    detail.with_context(**{_CONTEXT_KEY: _INTERNAL}).write({
                        "stock_line_ids": [Command.set(details.filtered(lambda line: line.move_id.id in ids).ids)],
                    })
            return result

    def _prepare_proposals(self, selected, lang):
        proposals = super()._prepare_proposals(selected, lang)
        if not self.repair_stock_values:
            return proposals
        operation = self.with_company(self.company_id).with_context(lang=lang, active_test=False)
        selected = selected.with_env(operation.env)
        return operation._prepare_stock_proposals(selected, proposals)

    def _stock_period_snapshot(self):
        company = self.company_id
        locks = {name: company._get_user_lock_date(name, ignore_exceptions=True)
                 for name in ("fiscalyear_lock_date", "tax_lock_date", "sale_lock_date", "purchase_lock_date")}
        locks["hard_lock_date"] = company.user_hard_lock_date
        return locks

    def _stock_history_snapshot(self, history):
        optional = [name for name in history._fields if name.startswith("consolidation_")]
        optional += [name for name in ("production_id", "raw_material_production_id", "sale_line_id",
                                       "purchase_line_id") if name in history._fields]
        history.check_access("read")
        history.move_line_ids.check_access("read")
        if history.account_move_id:
            history.account_move_id.check_access("read")
        self._stock_analytic_lines(history)
        return _json_value({
            "moves": history.sorted("id").read(_MOVE_FIELDS + optional),
            "lines": history.move_line_ids.sorted("id").read(_ML_FIELDS),
            "analytic_links": {str(move.id): move.sudo().analytic_account_line_ids.ids for move in history},
        })

    def _stock_analytic_lines(self, moves):
        # Inspect relation IDs only, then enforce the caller's access on every
        # actual record. An empty relation must not require Analytic Accounting
        # permissions merely to establish that no analytic record exists.
        lines = moves.sudo().analytic_account_line_ids.with_env(self.env)
        if lines:
            lines.check_access("read")
        return lines

    def _read_stock_history(self, products):
        domain = [("company_id", "=", self.company_id.id), ("product_id", "in", products.ids)]
        history = self.env["stock.move"].search(domain, order="id")
        # Count only: do not read hidden amounts or prove history from a subset.
        if self.env["stock.move"].sudo().search_count(domain) != len(history):
            raise AccessError(self.env._("Access to the complete stock history is required for repair."))
        return history

    def _stock_exclusion(self, move, lines, selected, history, locks, returns):
        product = move.product_id
        order = lines.order_id
        if not move.picking_id.pos_order_id:
            return self.env._("Aggregate session stock sources cannot be repaired."), False
        if len(order) != 1 or not lines or (lines - selected):
            return self.env._("All POS lines using this stock issue must be selected."), False
        if order.state not in ("paid", "done") or order.session_id.state != "closed":
            return self.env._("Only completed sales in closed sessions can repair stock values."), False
        if move.picking_id not in order.picking_ids or move.picking_id.pos_order_id != order:
            return self.env._("Aggregate session stock sources cannot be repaired."), False
        if product.cost_method != "fifo" or product.valuation != "periodic":
            return self.env._("Stock repair requires current FIFO and periodic valuation."), False
        if not product.is_storable or product.tracking != "none" or product.lot_valuated:
            return self.env._("Only untracked company-owned storable products can be repaired."), False
        if any(line.qty <= 0 or line._cost_recompute_unsupported_reason() for line in lines):
            return self.env._("Returns, corrections, kits and combo structures cannot be repaired."), False
        if any(lines.mapped("refund_orderline_ids")) or move.origin_returned_move_id:
            return self.env._("A related POS return requires separate review."), False
        if returns.filtered(lambda item: item.origin_returned_move_id == move):
            return self.env._("A non-cancelled stock return requires separate review."), False
        if order.account_move or move.account_move_id or self._stock_analytic_lines(move):
            return self.env._("Linked invoices, accounting or analytic entries prevent stock repair."), False
        if move._get_analytic_distribution() or move._should_create_account_move():
            return self.env._("Unresolved financial or analytic effects prevent stock repair."), False
        relevant_dates = [move.date.date(), order.date_order.date()]
        if any(limit and any(day <= limit for day in relevant_dates) for limit in locks.values()):
            return self.env._("The stock issue or POS order belongs to a locked period."), False
        template = product.product_tmpl_id
        if "merged_into_id" in template._fields and (template.merged_into_id or template.merged_source_ids):
            return self.env._("Consolidated products require separate valuation review."), False
        active = order.picking_ids.move_ids.filtered(lambda item: item.product_id == product and item.state != "cancel")
        if any(item.state != "done" or not item.is_out for item in active):
            return self.env._("Related stock processing is not a completed direct sale."), False
        if product.uom_id.compare(sum(lines.mapped("qty")), sum(item._get_valued_qty() for item in active)):
            return self.env._("Selected POS quantities do not fully cover the stock source."), False
        if move.cost_repair_line_id:
            return self.env._("This movement already has a stock repair."), False
        earlier = history.filtered(lambda item: item.state == "done" and item.date <= move.date)
        if earlier.filtered(lambda item: item != move and item.date == move.date):
            return self.env._("Equal movement timestamps make the source order ambiguous."), False
        receipts = earlier.filtered("is_in")
        if len(receipts) != 1:
            return self.env._("Exactly one earlier supplier receipt is required."), False
        receipt = receipts
        if receipt.date >= move.date or receipt.location_id.usage != "supplier" or (
            receipt.location_dest_id != move.location_id or move.location_id.usage != "internal"
        ):
            return self.env._("The supplier receipt must strictly precede the issue in the same storage location."), False
        consumed = 0.0
        for item in earlier.sorted("date"):
            if item.company_id != self.company_id or item.product_uom != product.uom_id:
                return self.env._("Historical company and product units must match."), False
            if any(item[name] for name in item._fields if name.startswith("consolidation_")):
                return self.env._("Consolidation movements cannot prove a simple receipt basis."), False
            if any(item[name] for name in ("production_id", "raw_material_production_id") if name in item._fields):
                return self.env._("Manufacturing history cannot prove a simple receipt basis."), False
            if item.move_line_ids.filtered(lambda ml: ml.owner_id or ml.lot_id or not ml.picked
                                           or ml.location_id != item.location_id
                                           or ml.location_dest_id != item.location_dest_id):
                return self.env._("Ownership, tracking or storage changes make the history unsupported."), False
            qty = item._get_valued_qty()
            if not math.isfinite(qty) or qty <= 0:
                return self.env._("Historical movements require positive finite valued quantities."), False
            if item == receipt:
                continue
            if not item.is_out or item.location_id != receipt.location_dest_id or item.location_dest_id.usage != "customer":
                return self.env._("Adjustments and internal transfers make the receipt basis ambiguous."), False
            if item.date <= receipt.date:
                return self.env._("Historical negative stock prevents a receipt-based repair."), False
            consumed += qty
        receipt_qty = receipt._get_valued_qty()
        if not math.isfinite(receipt.value) or receipt.value <= 0:
            return self.env._("The receipt has no positive finite recorded value."), False
        if product.uom_id.compare(consumed, receipt_qty) > 0:
            return self.env._("Earlier consumption leaves insufficient receipt quantity for this issue."), False
        return False, receipt

    def _prepare_stock_proposals(self, selected, proposals, return_plans=False):
        moves_by_line = {}
        targets = self.env["stock.move"]
        for line in selected:
            pickings = line.order_id.picking_ids or line.order_id.session_id.picking_ids
            moves = pickings.move_ids.filtered(lambda move: move.product_id == line.product_id and move.state != "cancel")
            moves.check_access("read")
            if any(move.company_id != self.company_id for move in moves):
                raise AccessError(self.env._("Stock sources must belong to the operation company."))
            zeros = moves.filtered(lambda move: math.isfinite(move.value) and self.company_id.currency_id.is_zero(move.value))
            moves_by_line[line.id] = zeros
            targets |= zeros
        history = self._read_stock_history(targets.product_id)
        histories = history.grouped("product_id")
        digests = {product: hashlib.sha256(json.dumps(
            self._stock_history_snapshot(moves), sort_keys=True,
        ).encode()).hexdigest() for product, moves in histories.items()}
        locks = self._stock_period_snapshot()
        plans = {}
        order_domain = [("picking_ids", "in", targets.picking_id.ids)]
        linked_orders = self.env["pos.order"].search(order_domain)
        if self.env["pos.order"].sudo().search_count(order_domain) != len(linked_orders):
            raise AccessError(self.env._("Access to every POS order using the stock source is required."))
        line_domain = [("order_id", "in", linked_orders.ids), ("product_id", "in", targets.product_id.ids)]
        linked_pos_lines = self.env["pos.order.line"].search(line_domain)
        if self.env["pos.order.line"].sudo().search_count(line_domain) != len(linked_pos_lines):
            raise AccessError(self.env._("Access to every POS line using the stock source is required."))
        return_domain = [("origin_returned_move_id", "in", targets.ids), ("state", "!=", "cancel")]
        returns = self.env["stock.move"].search(return_domain)
        if self.env["stock.move"].sudo().search_count(return_domain) != len(returns) or any(
            company != self.company_id for company in returns.company_id
        ):
            raise AccessError(self.env._("All related returns must be accessible in the operation company."))
        orders_by_picking = {}
        for order in linked_orders:
            for picking in order.picking_ids:
                orders_by_picking[picking.id] = orders_by_picking.get(picking.id, self.env["pos.order"]) | order
        for move in targets.sorted("id"):
            move_history = histories.get(move.product_id, self.env["stock.move"])
            orders = orders_by_picking.get(move.picking_id.id, self.env["pos.order"])
            linked_lines = orders.lines.filtered(lambda line: line.product_id == move.product_id)
            linked_lines.check_access("read")
            reason, receipt = self._stock_exclusion(move, linked_lines, selected, move_history, locks, returns)
            value = 0 if reason else self.company_id.currency_id.round(
                receipt.value * move._get_valued_qty() / receipt._get_valued_qty()
            )
            if not reason and (not math.isfinite(value) or value <= 0):
                reason = self.env._("The proposed stock value must be positive and finite.")
            plans[move.id] = {
                "move_id": move.id, "receipt_id": receipt.id if receipt else False,
                "company_id": self.company_id.id, "currency_id": self.company_id.currency_id.id,
                "product_id": move.product_id.id, "quantity": move._get_valued_qty(),
                "old_value": move.value, "new_value": value,
                "status": "skipped" if reason else "repair", "skip_reason": reason or False,
                "warning": self.env._(
                    "This corrects historical valuation using the receipt's current recorded value. "
                    "It does not prove FIFO applied at the sale date. Supplier billing may still "
                    "change the receipt value; later changes will not update this repair automatically."
                ),
                "pos_line_ids": [Command.set(linked_lines.ids)],
                "snapshot": {"history_digest": digests.get(move.product_id),
                             "linked_lines": linked_lines.sorted("id").read(["order_id", "qty", "product_id"]),
                             "locks": _json_value(locks)},
            }
        # A stock source shared by several moves/lines is applied as one group.
        # One excluded move must not leave a partial repair of that same source.
        proposals_by_id = {proposal["pos_line_id"]: proposal for proposal in proposals}
        for line in selected:
            group = [plans[move.id] for move in moves_by_line[line.id]]
            reasons = [plan["skip_reason"] for plan in group if plan["status"] == "skipped"]
            if proposals_by_id[line.id]["skip_reason"]:
                reasons.append(proposals_by_id[line.id]["skip_reason"])
            if reasons:
                for plan in group:
                    plan.update(status="skipped", skip_reason=reasons[0], new_value=0)
        for proposal in proposals:
            line = selected.browse(proposal["pos_line_id"])
            group = [plans[move.id] for move in moves_by_line[line.id]]
            reason = next((plan["skip_reason"] for plan in group if plan["status"] == "skipped"), False)
            # Preserve an existing unsupported-line reason before proposing writes.
            reason = reason or proposal["skip_reason"]
            if group and not reason:
                valued = self.env["stock.move"].browse(proposal["move_ids"][0][2])
                qty = sum(move._get_valued_qty() for move in valued)
                unit = sum(plans[move.id]["new_value"] if move.id in plans else move.value for move in valued) / qty
                new_cost = line.qty * line.product_id.cost_currency_id._convert(
                    unit, line.currency_id, self.company_id, line.order_id.date_order, round=False,
                )
                digits = self.env["decimal.precision"].precision_get("Product Price")
                status = "changed" if float_compare(line.total_cost, new_cost, precision_digits=digits) else (
                    "unchanged" if line.is_total_cost_computed else "completion"
                )
                proposal.update(new_cost=new_cost, new_computed=True, zero_source=False, status=status)
            elif group:
                proposal.update(status="skipped", skip_reason=reason, new_cost=0, zero_source=False,
                                new_computed=line.is_total_cost_computed)
                for plan in group:
                    plan.update(status="skipped", skip_reason=reason, new_value=0)
            proposal["snapshot"].update({
                # The complete evidence is stored once per operation and stock
                # issue. A shared issue must not duplicate 1000 linked lines in
                # each of 1000 POS snapshots.
                "stock_plan": [plan["move_id"] for plan in group],
                "repair_versions": [line.product_id.cost_recompute_revision,
                                    line.order_id.cost_recompute_revision,
                                    line.currency_id.cost_recompute_revision,
                                    line.product_id.cost_currency_id.cost_recompute_revision],
                "repair_product": [line.product_id.tracking, line.product_id.valuation,
                                   line.product_id.lot_valuated],
                "repair_locks": _json_value(locks),
                "repair_returns": returns.sorted("id").ids,
                "repair_proposed_cost": proposal["new_cost"],
            })
            proposal["snapshot"] = _json_value(proposal["snapshot"])
        plan_digests = {move_id: hashlib.sha256(json.dumps(
            _json_value(plan), sort_keys=True,
        ).encode()).hexdigest() for move_id, plan in plans.items()}
        for proposal in proposals:
            proposal["snapshot"]["stock_plan"] = [
                [move_id, plan_digests[move_id]] for move_id in proposal["snapshot"]["stock_plan"]
            ]
        return (proposals, plans) if return_plans else proposals

    def _lock_sources(self, selected):
        super()._lock_sources(selected)
        if not self.repair_stock_values:
            return
        ids = {move["id"] for evidence in (self.stock_evidence or {}).values()
               for move in evidence["moves"]}
        moves = self.env["stock.move"].browse(sorted(ids))
        currencies = selected.currency_id | selected.product_id.cost_currency_id
        sources = [self.company_id.parent_ids, currencies, moves.picking_id, moves,
                   moves.move_line_ids, moves.location_id | moves.location_dest_id,
                   moves.account_move_id, self._stock_analytic_lines(moves)]
        for records in sources:
            if not records:
                continue
            records.check_access("read")
            records.sorted("id").lock_for_update()
            records.invalidate_recordset()
        # Computed non-stored settings and conversions can have been cached
        # before the parent locks; the DB snapshot remains protected by versions.
        self.env.invalidate_all()

    def _apply_stock_plan(self):
        super()._apply_stock_plan()
        if not self.repair_stock_values:
            return
        if self.stock_repair_count and not self.acknowledge_stock_repair:
            raise UserError(self.env._("Acknowledge the historical stock-value changes before applying."))
        # Module lifecycle metadata is global; stock managers do not need
        # Settings access. No business record is read or written with sudo.
        module = self.env["ir.module.module"].sudo().search([("name", "=", "pos_cost_recompute")])
        module.lock_for_update()
        module.invalidate_recordset()
        if module.state not in ("installed", "to upgrade"):
            raise UserError(self.env._("Stock repairs cannot be applied while the module is being removed."))
        if self.stock_repair_count:
            # A remover whose snapshot predates this repair must conflict even
            # if its initial check could not see the new audit/link yet.
            _touch(module)
        for detail in self.stock_line_ids.filtered(lambda line: line.status == "repair"):
            detail._apply_reviewed_value()


class PosCostRecomputeLine(models.Model):
    _inherit = "pos.cost.recompute.line"

    stock_line_ids = fields.Many2many("pos.cost.recompute.stock.line", readonly=True, check_company=True)
