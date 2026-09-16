import hashlib
import json
import math
from collections import defaultdict

from odoo import fields
from odoo.exceptions import AccessError, UserError


_INTERNAL = object()
_KEY = "pos_historical_stock_internal"
_VALUATION = object()
_VALUATION_KEY = "pos_historical_stock_valuation"


def internal(env):
    return env.context.get(_KEY) is _INTERNAL


def check_permission(env):
    if not env.user.has_group("pos_historical_stock_writeoff.group_historical_stock"):
        raise AccessError(env._("Historical stock operations require dedicated permission."))


def check_period(env, company, timestamp):
    day = fields.Datetime.to_datetime(timestamp).date()
    limits = [company._get_user_lock_date(name, ignore_exceptions=True) for name in (
        "fiscalyear_lock_date", "tax_lock_date", "sale_lock_date", "purchase_lock_date",
    )] + [company.user_hard_lock_date]
    # Only the closing boundary is read with elevated rights, never accounting amounts.
    closing = company.sudo()._get_last_closing_date()
    if any(limit and day <= limit for limit in limits) or (
        closing and day <= fields.Datetime.to_datetime(closing).date()
    ):
        raise UserError(env._("The historical operation overlaps a locked or closed valuation period."))


def read_history(env, company, products):
    products.check_access("read")
    domain = [("company_id", "=", company.id), ("product_id", "in", products.ids)]
    history = env["stock.move"].search(domain, order="date, id")
    if env["stock.move"].sudo().search_count(domain) != len(history):
        raise AccessError(env._("Access to the complete stock history is required."))
    history.move_line_ids.check_access("read")
    return history


def digest(history):
    values = {
        "moves": history.sorted("id").read([
            "state", "product_id", "company_id", "date", "quantity", "product_uom",
            "product_uom_qty", "value", "location_id", "location_dest_id", "picking_id",
            "account_move_id", "origin_returned_move_id", "cost_repair_line_id",
        ]),
        "lines": history.move_line_ids.sorted("id").read([
            "move_id", "date", "quantity", "product_id", "product_uom_id", "lot_id",
            "owner_id", "location_id", "location_dest_id", "picked",
        ]),
        "versions": history.product_id.sorted("id").read(["cost_recompute_revision"]),
    }
    return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


def validate_history(env, company, products, location, timestamp, demands=None):
    """Prove a direct, company-owned FIFO history; never reconstruct missing receipts."""
    demands = demands or {}
    check_period(env, company, timestamp)
    history = read_history(env, company, products)
    now = fields.Datetime.now()
    for product in products:
        if (not product.is_storable or product.tracking != "none" or product.lot_valuated
                or product.cost_method != "fifo" or product.valuation != "periodic"):
            raise UserError(env._(
                "%(product)s requires untracked company-owned stock with FIFO and periodic valuation.",
                product=product.display_name,
            ))
        template = product.product_tmpl_id
        if "merged_into_id" in template._fields and (template.merged_into_id or template.merged_source_ids):
            if not template._has_full_consolidation_history(company):
                raise UserError(env._(
                    "%(product)s still has separate source history. Open Merge Full History on its product card and convert all absorbed sources first.",
                    product=product.display_name,
                ))
        records = history.filtered(lambda move: move.product_id == product and move.state == "done")
        balance = 0.0
        at_date = 0.0
        demand = demands.get(product.id, 0.0)
        if not math.isfinite(demand):
            raise UserError(env._("The total historical quantity must be finite."))
        dates = defaultdict(set)
        for move in records:
            quantity = move._get_valued_qty()
            incoming = move.location_id.usage in ("supplier", "inventory") and move.location_dest_id == location and move.is_in
            outgoing = move.location_id == location and move.location_dest_id.usage == "customer" and move.is_out
            if not (incoming or outgoing) or move.origin_returned_move_id or move.cost_repair_line_id:
                raise UserError(env._("Returns, transfers or previously repaired stock require separate valuation review."))
            if move.date > now or not math.isfinite(quantity) or quantity <= 0:
                raise UserError(env._("Stock history contains an unsupported date or quantity."))
            if move.account_move_id or move.sudo().analytic_account_line_ids:
                raise UserError(env._("Existing accounting or analytic entries prevent historical stock valuation changes."))
            if move.move_line_ids.filtered(lambda line: line.owner_id or line.lot_id or line.package_id
                                          or line.result_package_id or not line.picked
                                          or line.location_id != move.location_id
                                          or line.location_dest_id != move.location_dest_id):
                raise UserError(env._("Tracked, packaged or third-party stock history is not supported."))
            if incoming and (not math.isfinite(move.value) or move.value <= 0):
                raise UserError(env._("Historical receipts must have a positive recorded value."))
            dates[move.date].add("in" if incoming else "out")
            balance += quantity if incoming else -quantity
            if move.date <= timestamp:
                at_date = balance
            adjusted = balance - (demand if move.date >= timestamp else 0)
            if product.uom_id.compare(adjusted, 0) < 0:
                raise UserError(env._("Historical consumption would cause a stock shortage for %(product)s on %(date)s.",
                                     product=product.display_name, date=move.date))
        if any(len(kinds) > 1 for kinds in dates.values()) or "in" in dates.get(timestamp, set()):
            raise UserError(env._("Equal receipt and issue timestamps make historical valuation ambiguous."))
        if product.uom_id.compare(at_date, demand) < 0:
            raise UserError(env._("Insufficient historical stock for %(product)s: available %(available)s, required %(required)s.",
                                 product=product.display_name, available=at_date, required=demand))
        quants = env["stock.quant"].search([
            ("product_id", "=", product.id), ("location_id", "=", location.id),
            ("company_id", "=", company.id),
        ])
        if quants.filtered(lambda q: q.owner_id or q.lot_id or q.package_id):
            raise UserError(env._("Tracked, packaged or third-party stock history is not supported."))
        quantity = sum(quants.mapped("quantity"))
        if product.uom_id.compare(balance, quantity):
            raise UserError(env._("Recorded movements do not reconcile with current stock for %(product)s.", product=product.display_name))
        if product.uom_id.compare(quantity - sum(quants.mapped("reserved_quantity")), demand) < 0:
            raise UserError(env._("Current unreserved stock is insufficient for %(product)s.", product=product.display_name))
    picks = history.filtered(lambda move: move.state == "done" and move.is_out and move.date >= timestamp).picking_id
    picks = picks.filtered(lambda picking: not picking.historical_pos_order_id)
    orders = (picks.pos_order_id | picks.pos_session_id.order_ids).filtered(lambda order: order.state in ("paid", "done", "invoiced"))
    lines = orders.lines.filtered(lambda line: line.product_id in products)
    for line in lines:
        proposal = line._prepare_cost_recompute_proposal(lines)
        if proposal["skip_reason"]:
            raise UserError(env._("Historical recomputation cannot include this POS source: %(reason)s", reason=proposal["skip_reason"]))
    return history


def fifo_values(moves):
    """Use standard FIFO just before each issue, including equal-time issue batches."""
    result = {}
    for batch in moves.grouped(lambda move: (move.product_id, move.date)).values():
        remaining = sum(move._get_valued_qty() for move in batch)
        for move in batch.sorted("id"):
            quantity = move._get_valued_qty()
            result[move.id] = move.product_id.with_context(
                fifo_qty_already_processed=-remaining,
            )._run_fifo(quantity, at_date=move.date)
            if not math.isfinite(result[move.id]) or result[move.id] < 0:
                raise UserError(moves.env._("Historical FIFO returned an invalid valuation."))
            remaining -= quantity
    return result
