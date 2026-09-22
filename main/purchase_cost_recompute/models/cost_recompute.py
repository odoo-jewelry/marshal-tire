import math
from collections import defaultdict
from datetime import timedelta

from odoo import fields, models
from odoo.exceptions import UserError

from .pos_order_line import _COMPANY_KEY, _POS_LINE_IDS_KEY


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _check_purchase_history_period(self, timestamp):
        company = self.env.company
        day = fields.Datetime.to_datetime(timestamp).date()
        limits = [company._get_user_lock_date(name, ignore_exceptions=True) for name in (
            "fiscalyear_lock_date", "tax_lock_date", "sale_lock_date", "purchase_lock_date",
        )] + [company.user_hard_lock_date]
        # Read only the closing boundary with elevated rights, never its amounts.
        closing = company.sudo()._get_last_closing_date()
        if any(limit and day <= limit for limit in limits) or (
            closing and day <= fields.Datetime.to_datetime(closing).date()
        ):
            raise UserError(self.env._(
                "Purchase cost correction overlaps a locked or closed valuation period.",
            ))

    def _prepare_purchase_history_plan(self, changes, cutoff):
        lines = self.env["purchase.order.line"].browse([line.id for line, _price in changes])
        products = lines.product_id
        products.check_access("write")
        products.product_tmpl_id.check_access("write")
        products.read(["standard_price", "cost_currency_id"])
        history = self._purchase_cost_search("stock.move", [
            ("company_id", "=", self.env.company.id),
            ("product_id", "in", products.ids),
        ]).sorted(lambda move: (move.date, move.id))
        move_lines = self._purchase_cost_search("stock.move.line", [
            ("move_id", "in", history.ids),
        ])
        scraps = self._purchase_cost_search("stock.scrap", [
            ("id", "in", history.scrap_id.ids),
        ])
        historical_pickings = self.env["stock.picking"]
        historical_sources = self.env["pos.order"]
        historical_lines = self.env["pos.order.line"]
        historical_sessions = self.env["pos.session"]
        if "historical_pos_order_id" in historical_pickings._fields:
            historical_pickings = history.picking_id.filtered(
                lambda picking: picking.state != "cancel" and picking.historical_pos_order_id
            )
            historical_sources = historical_pickings.historical_pos_order_id
            historical_lines = self._purchase_cost_search("pos.order.line", [
                ("order_id", "in", historical_sources.ids),
            ])
            historical_sessions = (historical_sources.session_id
                                   | historical_pickings.historical_session_id)
        for records in (historical_sources, historical_sessions, historical_lines,
                        history.picking_id, scraps, history, move_lines,
                        history.location_id | history.location_dest_id):
            records.check_access("read")
            self._lock_purchase_cost_records(records)

        done = history.filtered(lambda move: move.state == "done")
        receipts = done.filtered(lambda move: move.purchase_line_id in lines)
        missing_lines = lines - receipts.purchase_line_id
        if missing_lines:
            line = missing_lines[0]
            raise UserError(self.env._(
                "%(order)s, %(product)s: a completed receipt is required to prove historical cost.",
                order=line.order_id.display_name, product=line.product_id.display_name,
            ))
        start_by_product = {
            product.id: min(receipts.filtered(lambda move: move.product_id == product).mapped("date"))
            for product in products
        }
        issues = self.env["stock.move"]
        returns = self.env["stock.move"]
        inventory_gains = self.env["stock.move"]
        inventory_losses = self.env["stock.move"]
        scrap_issues = self.env["stock.move"]
        locations = {}
        for product in products:
            records = history.filtered(lambda move: move.product_id == product)
            (location, product_issues, product_returns, product_gains,
             product_losses, product_scraps) = self._validate_purchase_product_history(
                product, records, start_by_product[product.id], cutoff,
            )
            locations[product.id] = location
            issues |= product_issues
            returns |= product_returns
            inventory_gains |= product_gains
            inventory_losses |= product_losses
            scrap_issues |= product_scraps
        changed_moves = receipts | issues | returns | inventory_gains
        changed_moves.check_access("write")
        self._check_purchase_valuation_protection(changed_moves)
        for timestamp in set(changed_moves.mapped("date")):
            self._check_purchase_history_period(timestamp)
        historical_issues = issues.filtered(lambda move: move.picking_id in historical_pickings)
        if historical_issues:
            historical_issues._check_historical_purchase_valuation()
        pos_plan = self._prepare_purchase_pos_plan(
            (issues - inventory_losses - scrap_issues | returns) - historical_issues,
            products, start_by_product, cutoff,
            historical_sources=historical_sources,
        )
        return {
            "products": products,
            "history": history,
            "receipts": receipts,
            "issues": issues,
            "historical_issues": historical_issues,
            "returns": returns,
            "inventory_gains": inventory_gains,
            "inventory_losses": inventory_losses,
            "scrap_issues": scrap_issues,
            "locations": locations,
            "start_by_product": start_by_product,
            "pos_plan": pos_plan,
        }

    def _validate_purchase_product_history(self, product, history, start, cutoff):
        if (product.type != "consu" or product.tracking != "none" or product.lot_valuated
                or product.cost_method != "fifo" or product.valuation != "periodic"):
            raise UserError(self.env._(
                "%(product)s requires goods without lot/serial tracking, FIFO and periodic valuation.",
                product=product.display_name,
            ))
        template = product.product_tmpl_id.sudo().with_context(active_test=False)
        if "merged_into_id" in template._fields:
            if template.merged_into_id:
                raise UserError(self.env._(
                    "Purchase correction cannot target absorbed product %(product)s.",
                    product=product.display_name,
                ))
            if template.merged_source_ids:
                proof = getattr(template, "_has_full_consolidation_history", None)
                if not proof or not proof(self.env.company):
                    raise UserError(self.env._(
                        "%(product)s requires proven full history consolidation; absorbed cards still have history or lack consolidation evidence.",
                        product=product.display_name,
                    ))
        if history.filtered(lambda move: move.state not in ("done", "cancel")):
            raise UserError(self.env._(
                "Finish or cancel all pending stock movements for %(product)s first.",
                product=product.display_name,
            ))
        done = history.filtered(lambda move: move.state == "done")
        locations = (done.location_id | done.location_dest_id).filtered(
            lambda location: location.usage == "internal"
        )
        if len(locations) != 1 or not locations.is_valued_internal:
            raise UserError(self.env._(
                "%(product)s requires exactly one internal stock location.",
                product=product.display_name,
            ))
        location = locations
        issues = self.env["stock.move"]
        returns = self.env["stock.move"]
        inventory_gains = self.env["stock.move"]
        inventory_losses = self.env["stock.move"]
        scrap_issues = self.env["stock.move"]
        dates = defaultdict(set)
        returned_quantities = defaultdict(float)
        balance = 0.0
        last_incoming = self.env["stock.move"]
        for move in done:
            incoming = (
                move.location_id.usage in ("supplier", "inventory")
                and move.location_dest_id == location and move.is_in and not move.is_out
                and not move.origin_returned_move_id
            )
            inventory_gain = incoming and move.location_id.usage == "inventory"
            if inventory_gain:
                incoming = bool(move.is_inventory and not move.scrap_id and not move.purchase_line_id)
            outgoing = (
                move.location_id == location and move.location_dest_id.usage == "customer"
                and move.is_out and not move.is_in and not move.origin_returned_move_id
            )
            inventory_loss = (
                move.location_id == location and move.location_dest_id.usage == "inventory"
                and move.is_out and not move.is_in and not move.origin_returned_move_id
                and move.is_inventory and not move.scrap_id
                and not move.purchase_line_id
            )
            scrap_issue = (
                move.location_id == location and move.location_dest_id.usage == "inventory"
                and move.is_out and not move.is_in and not move.origin_returned_move_id
                and bool(move.scrap_id) and not move.is_inventory
                and not move.purchase_line_id
            )
            if scrap_issue:
                scrap = move.scrap_id
                scrap_issue = (
                    scrap.state == "done" and scrap.company_id == self.env.company
                    and scrap.product_id == product and scrap.product_uom_id == product.uom_id
                    and scrap.location_id == location
                    and scrap.scrap_location_id == move.location_dest_id
                    and scrap.picking_id == move.picking_id
                    and scrap.move_ids == move
                    and product.uom_id.compare(scrap.scrap_qty, move.quantity) == 0
                )
            customer_return = (
                move.location_id.usage == "customer" and move.location_dest_id == location
                and move.is_in and not move.is_out and bool(move.origin_returned_move_id)
            )
            if ((move.is_inventory and not (inventory_gain or inventory_loss))
                    or (move.scrap_id and not scrap_issue)):
                raise UserError(self.env._(
                    "Unsupported receipt, return or transfer in %(product)s: %(move)s.",
                    product=product.display_name, move=move.display_name,
                ))
            if not (incoming or outgoing or inventory_loss or scrap_issue or customer_return) or move.is_dropship:
                raise UserError(self.env._(
                    "Unsupported receipt, return or transfer in %(product)s: %(move)s.",
                    product=product.display_name, move=move.display_name,
                ))
            if move.purchase_line_id and not incoming:
                raise UserError(self.env._("Supplier returns and mixed purchase sources are not supported."))
            quantity = move._get_valued_qty()
            if (not move.date or move.date > cutoff or not math.isfinite(quantity) or quantity <= 0
                    or not math.isfinite(move.quantity) or not math.isfinite(move.value)
                    or move.value < 0 or move.product_uom != product.uom_id
                    or product.uom_id.compare(move.quantity, quantity)):
                raise UserError(self.env._(
                    "%(move)s has an unsupported date, quantity, unit or recorded value.",
                    move=move.display_name,
                ))
            source_lines = move.move_line_ids
            if not source_lines or source_lines.filtered(
                lambda line: line.owner_id or line.lot_id or line.package_id
                or line.result_package_id or not line.picked
                or line.company_id != self.env.company or line.product_id != product
                or line.product_uom_id != product.uom_id
                or line.location_id != move.location_id
                or line.location_dest_id != move.location_dest_id
                or not math.isfinite(line.quantity) or line.quantity <= 0
            ):
                raise UserError(self.env._(
                    "%(move)s has tracked, packaged, third-party or inconsistent stock details.",
                    move=move.display_name,
                ))
            self._check_purchase_protected_history(move)
            if incoming or customer_return:
                if move.value <= 0:
                    raise UserError(self.env._(
                        "%(move)s requires a positive recorded incoming value.", move=move.display_name,
                    ))
                if customer_return:
                    origin = move.origin_returned_move_id
                    origin.check_access("read")
                    if (origin not in done or origin.company_id != self.env.company
                            or origin.product_id != product or not origin.is_out or origin.is_in
                            or origin.location_id != location
                            or origin.location_dest_id != move.location_id
                            or origin.date >= move.date or origin.origin_returned_move_id):
                        raise UserError(self.env._(
                            "%(move)s has no valid earlier customer issue for its return.",
                            move=move.display_name,
                        ))
                    returned_quantities[origin.id] += quantity
                    if product.uom_id.compare(returned_quantities[origin.id], origin._get_valued_qty()) > 0:
                        raise UserError(self.env._(
                            "Customer returns exceed the original quantity of %(move)s.",
                            move=origin.display_name,
                        ))
                    if move.date >= start:
                        returns |= move
                balance += quantity
                last_incoming = move
                dates[move.date].add(
                    "gain" if inventory_gain else "return" if customer_return else "receipt"
                )
                if inventory_gain and move.date >= start:
                    inventory_gains |= move
            else:
                # An empty historical FIFO stack must have a proven earlier
                # incoming value; today's card cost is never evidence.
                if product.uom_id.compare(balance, 0) <= 0 and not last_incoming:
                    raise UserError(self.env._(
                        "No earlier incoming value proves the historical shortage cost of %(move)s.",
                        move=move.display_name,
                    ))
                balance -= quantity
                dates[move.date].add("out")
                if move.date >= start:
                    issues |= move
                    if inventory_loss:
                        inventory_losses |= move
                    elif scrap_issue:
                        scrap_issues |= move
        if any("out" in directions and len(directions) > 1
               or "gain" in directions and len(directions) > 1
               for directions in dates.values()):
            raise UserError(self.env._(
                "Equal receipt and issue timestamps make %(product)s historical costs ambiguous.",
                product=product.display_name,
            ))
        quants = self._purchase_cost_search("stock.quant", [
            ("product_id", "=", product.id), ("company_id", "=", self.env.company.id),
            ("location_id.usage", "=", "internal"),
        ])
        self._lock_purchase_cost_records(quants)
        if quants.filtered(lambda quant: quant.owner_id or quant.lot_id or quant.package_id
                           or not math.isfinite(quant.quantity)
                           or quant.location_id != location and not product.uom_id.is_zero(quant.quantity)):
            raise UserError(self.env._(
                "Current stock for %(product)s has unsupported ownership, tracking or locations.",
                product=product.display_name,
            ))
        if product.uom_id.compare(balance, sum(quants.mapped("quantity"))):
            raise UserError(self.env._(
                "Recorded movements do not reconcile with current stock for %(product)s.",
                product=product.display_name,
            ))
        return location, issues, returns, inventory_gains, inventory_losses, scrap_issues

    def _check_purchase_protected_history(self, move):
        for name in ("cost_repair_line_id", "historical_cost_line_id"):
            if name in move._fields and move[name]:
                raise UserError(self.env._(
                    "%(move)s belongs to a protected previous cost correction.", move=move.display_name,
                ))
        picking = move.picking_id
        if ("historical_pos_order_id" in picking._fields and picking.historical_pos_order_id
                and (not hasattr(move, "_check_historical_purchase_valuation")
                     or not hasattr(move, "_write_historical_purchase_values"))):
            raise UserError(self.env._(
                "%(move)s requires the historical purchase valuation integration.", move=move.display_name,
            ))
        if any(move[name] for name in move._fields if name.startswith("consolidation_")):
            raise UserError(self.env._("Consolidated stock movements require separate valuation review."))

    def _check_purchase_valuation_protection(self, moves):
        manual = self._purchase_cost_search("product.value", [("move_id", "in", moves.ids)])
        if manual:
            raise UserError(self.env._("A manually adjusted stock value prevents purchase cost correction."))
        if moves.filtered("account_move_id") or any(
            # Only test whether protected accounting evidence exists.
            move.sudo().analytic_account_line_ids for move in moves
        ):
            raise UserError(self.env._(
                "Existing stock accounting or analytic entries prevent purchase cost correction.",
            ))
        if "stock.valuation.adjustment.lines" in self.env:
            adjustments = self._purchase_cost_search("stock.valuation.adjustment.lines", [
                ("move_id", "in", moves.ids), ("cost_id.state", "=", "done"),
            ])
            if adjustments:
                raise UserError(self.env._("Landed costs prevent purchase cost correction."))

    def _prepare_purchase_pos_plan(self, changed_moves, products, start_by_product, cutoff,
                                   historical_sources=None):
        source_ids = historical_sources.ids if historical_sources else []
        pickings = changed_moves.picking_id
        sessions = pickings.pos_session_id
        orders = self._purchase_cost_search("pos.order", [
            ("company_id", "=", self.env.company.id),
            ("id", "not in", source_ids),
            "|", ("picking_ids", "in", pickings.ids), ("session_id", "in", sessions.ids),
        ])
        lines = self._purchase_cost_search("pos.order.line", [
            ("company_id", "=", self.env.company.id),
            ("order_id", "not in", source_ids),
            ("product_id", "in", products.ids),
            "|", ("order_id", "in", orders.ids),
            "&", ("order_id.state", "in", ("paid", "done", "invoiced")),
            "&", ("order_id.date_order", ">=", min(start_by_product.values())),
            ("order_id.date_order", "<=", cutoff),
        ])
        orders |= lines.order_id
        for records in (orders, orders.session_id, lines, orders.config_id,
                        orders.picking_ids | orders.session_id.picking_ids):
            records.check_access("read")
            self._lock_purchase_cost_records(records)
        groups = {}
        for line in lines:
            order = line.order_id
            if (order not in pickings.pos_order_id and order.session_id not in sessions
                    and order.date_order < start_by_product[line.product_id.id]):
                continue
            # Cancelled or unpaid session lines do not own completed stock.
            if order.state not in ("paid", "done", "invoiced") and not order.picking_ids:
                continue
            moves, source, reason = line._cost_recompute_stock_source()
            active_moves = moves.filtered(lambda move: move.state != "cancel")
            if active_moves and not (active_moves & changed_moves):
                continue
            reason = reason or line._cost_recompute_unsupported_reason()
            if (not reason and "correction_root_id" in order._fields
                    and (order.sudo().search_count([("correction_root_id", "=", order.id)])
                         or self.env["pos.order.correction"].sudo().search_count([
                             ("root_order_id", "=", order.id), ("state", "=", "applied"),
                         ]))):
                # Hidden correction documents must not make a chain appear
                # eligible; inspect only their existence, never their amounts.
                reason = self.env._("Project correction chains require separate cost allocation.")
            if not reason and order.state not in ("paid", "done"):
                reason = self.env._("Only paid or completed POS orders can be recomputed.")
            if not reason and source == "session_moves" and order.session_id.state != "closed":
                reason = self.env._("A shared POS stock source requires a closed session.")
            if not reason and (not math.isfinite(line.qty) or line.product_uom_id != line.product_id.uom_id):
                reason = self.env._("POS quantities must be finite and use the product's base unit.")
            if not reason and order.shipping_date and line.product_id.cost_currency_id.is_zero(
                line._get_product_cost_with_moves(active_moves)
            ):
                reason = self.env._("Deferred-delivery zero-cost substitution requires separate review.")
            if reason:
                raise UserError(self.env._(
                    "Cannot recompute POS order %(order)s: %(reason)s",
                    order=order.display_name, reason=reason,
                ))
            line.check_access("write")
            order.check_access("write")
            (line.refunded_orderline_id | line.refund_orderline_ids).check_access("read")
            group_key = (line.product_id.id, tuple(sorted(active_moves.ids)))
            if group_key not in groups:
                groups[group_key] = {"lines": self.env["pos.order.line"], "moves": active_moves}
            groups[group_key]["lines"] |= line
        covered_moves = self.env["stock.move"]
        for group in groups.values():
            source_lines, moves = group["lines"], group["moves"]
            product = source_lines.product_id
            signs = {line.qty > 0 for line in source_lines}
            if len(signs) != 1 or product.uom_id.compare(
                abs(sum(source_lines.mapped("qty"))), sum(move._get_valued_qty() for move in moves),
            ):
                raise UserError(self.env._(
                    "POS stock quantities cannot be fully attributed for %(product)s.",
                    product=product.display_name,
                ))
            covered_moves |= moves
        required = changed_moves.filtered(
            lambda move: move.picking_id.pos_order_id or move.picking_id.pos_session_id
        )
        if required - covered_moves:
            raise UserError(self.env._("Some affected POS stock movements have no complete POS cost source."))
        self._check_purchase_pos_financial_sources(groups.values())
        currencies = lines.currency_id | lines.product_id.cost_currency_id
        rates = self._purchase_cost_search("res.currency.rate", [
            ("currency_id", "in", currencies.ids),
            ("company_id", "in", [False, self.env.company.id]),
        ])
        for records in (currencies, rates):
            self._lock_purchase_cost_records(records)
        return list(groups.values())

    def _check_purchase_pos_financial_sources(self, groups):
        # Resolve protected dependency identifiers only, never financial amounts.
        # Accounting read/write permissions are not required by this action.
        invoice_orders = {}
        for group in groups:
            for line in group["lines"]:
                invoice = line.order_id.sudo().account_move
                if invoice:
                    invoice_orders.setdefault(invoice.id, {})[line.product_id.id] = line.order_id
        pending = self.env["account.move"].sudo().browse(sorted(invoice_orders))
        while pending:
            family = pending[:1]._purchase_cost_document_family()
            origins = pending & family
            product_orders = {}
            for invoice in origins:
                product_orders.update(invoice_orders[invoice.id])
            order = next(iter(product_orders.values()))
            protected = self.env["account.move.line"].sudo().search([
                ("move_id", "in", family.ids),
                ("display_type", "=", "cogs"),
                ("product_id", "in", list(product_orders)),
            ], limit=1)
            if any(invoice.company_id != self.env.company for invoice in family):
                reason = self.env._("Related POS financial documents must belong to the order company.")
            elif protected:
                order = product_orders[protected.product_id.id]
                reason = self.env._("Related customer financial documents contain protected cost-of-goods-sold entries.")
            else:
                reason = False
            if reason:
                raise UserError(self.env._(
                    "Cannot recompute POS order %(order)s: %(reason)s",
                    order=order.display_name, reason=reason,
                ))
            pending -= family

    def _recompute_purchase_history(self, plan):
        # purchase_stock has already revalued all selected receipts from the
        # price/tax write, including prices unchanged by two-decimal rounding.
        if any(not math.isfinite(move.value) or move.value <= 0 for move in plan["receipts"]):
            raise UserError(self.env._("Corrected receipts require a positive finite stock value."))
        affected = plan["issues"] | plan["returns"] | plan["inventory_gains"]
        returns = plan["returns"]
        inventory_gains = plan["inventory_gains"]
        for product in plan["products"]:
            product_moves = affected.filtered(lambda move: move.product_id == product).sorted(
                lambda move: (move.date, move.id)
            )
            for timestamp, batch in product_moves.grouped("date").items():
                if batch & inventory_gains:
                    before = timestamp - timedelta(microseconds=1)
                    historical_product = product.with_context(to_date=before)
                    quantity_before = historical_product._with_valuation_context().qty_available
                    if product.uom_id.compare(quantity_before, 0) > 0:
                        stack, first_quantity = product._run_fifo_get_stack(at_date=before)
                        covered = first_quantity + sum(
                            move._get_valued_qty() for move in stack[1:]
                        )
                        if product.uom_id.compare(covered, quantity_before) < 0:
                            raise UserError(self.env._(
                                "No complete historical FIFO value proves the inventory gain cost."
                            ))
                        unit_cost = product._run_fifo(quantity_before, at_date=before) / quantity_before
                    else:
                        last_in = product._get_last_in(before)
                        unit_cost = last_in._get_price_unit() if last_in else 0.0
                    if not math.isfinite(unit_cost) or unit_cost <= 0:
                        raise UserError(self.env._(
                            "No earlier incoming value proves the inventory gain cost."
                        ))
                    for move in batch:
                        value = move._get_valued_qty() * unit_cost
                        if not math.isfinite(value) or value <= 0:
                            raise UserError(self.env._("Historical inventory gain has an invalid value."))
                        move.write({"value": value})
                    continue
                if batch & returns:
                    batch._set_value()
                    if any(not math.isfinite(move.value) or move.value <= 0 for move in batch):
                        raise UserError(self.env._("Corrected returns require a positive finite stock value."))
                    continue
                remaining = sum(move._get_valued_qty() for move in batch)
                for move in batch.sorted("id"):
                    quantity = move._get_valued_qty()
                    historical_product = product.with_context(fifo_qty_already_processed=-remaining)
                    stack, _first_quantity = historical_product._run_fifo_get_stack(at_date=timestamp)
                    if stack:
                        value = historical_product._run_fifo(quantity, at_date=timestamp)
                    else:
                        last_in = historical_product._get_last_in(timestamp)
                        if not last_in or last_in.date >= timestamp or last_in._get_valued_qty() <= 0:
                            raise UserError(self.env._(
                                "No earlier incoming value proves the historical shortage cost of %(move)s.",
                                move=move.display_name,
                            ))
                        value = quantity * last_in._get_price_unit()
                    if not math.isfinite(value) or value <= 0:
                        raise UserError(self.env._("Historical FIFO returned an invalid stock value."))
                    if move in plan["historical_issues"]:
                        move._write_historical_purchase_values({move.id: value})
                    else:
                        move.write({"value": value})
                    remaining -= quantity
        affected.invalidate_recordset(["remaining_qty", "remaining_value"])
        plan["products"].invalidate_recordset(["total_value", "avg_cost"])

    def _recompute_purchase_pos_costs(self, pos_plan):
        for group in pos_plan:
            lines, moves = group["lines"], group["moves"]
            if any(not math.isfinite(move.value) or move.value <= 0 for move in moves):
                raise UserError(self.env._("A POS stock source has an invalid corrected value."))
            lines.write({"is_total_cost_computed": False})
            lines.with_context(**{
                _COMPANY_KEY: self.env.company.id,
                _POS_LINE_IDS_KEY: tuple(lines.ids),
            })._compute_total_cost(moves)
            if any(not math.isfinite(line.total_cost) for line in lines):
                raise UserError(self.env._("POS cost recomputation returned a non-finite amount."))
