"""Read stock quantities and standard valuation sources for the report."""

from bisect import bisect_left
from collections import defaultdict
from datetime import timedelta

from odoo import api, models


class StockDynamicTurnoverSources(models.AbstractModel):
    _inherit = "stock.dynamic.turnover.report"

    @api.model
    def _collect(self, params):
        """Backtrack current owned quants through every completed movement."""
        company = params["company"]
        product_ids = params["products"].ids
        all_locations = params["all_locations"]
        owners = [False, company.partner_id.id]
        boundaries = {name: defaultdict(float) for name in ("current", "opening", "closing")}
        lines = []
        if not product_ids:
            return {"balances": boundaries, "lines": lines}
        Quant = self.env["stock.quant"].with_context(active_test=False)
        grouped = Quant._read_group([
            ("company_id", "=", company.id), ("product_id", "in", product_ids),
            ("location_id", "in", list(all_locations)), ("owner_id", "in", owners),
        ], ["product_id", "lot_id", "location_id"], ["quantity:sum"])
        for product, lot, location, quantity in grouped:
            key = (product.id, lot.id or 0, location.id)
            for balance in boundaries.values():
                balance[key] += quantity
        Line = self.env["stock.move.line"].with_context(active_test=False)
        found = Line.search_fetch([
            ("company_id", "=", company.id), ("product_id", "in", product_ids),
            ("move_id.state", "=", "done"), ("owner_id", "in", owners),
        ], ["product_id", "lot_id", "location_id", "location_dest_id",
            "quantity_product_uom", "move_id"])
        found.mapped("move_id").fetch(["date", "value", "state", "is_in", "is_out", "picking_id", "sale_line_id", "purchase_line_id", "scrap_id"])
        for line in found:
            move = line.move_id
            if not move.date or not line.quantity_product_uom:
                continue
            product_id = line.product_id.id
            lot_id = line.lot_id.id or 0
            qty = line.quantity_product_uom
            src = (product_id, lot_id, line.location_id.id)
            dst = (product_id, lot_id, line.location_dest_id.id)
            if move.date >= params["start"]:
                if src[2] in all_locations:
                    boundaries["opening"][src] += qty
                if dst[2] in all_locations:
                    boundaries["opening"][dst] -= qty
            if move.date >= params["end"]:
                if src[2] in all_locations:
                    boundaries["closing"][src] += qty
                if dst[2] in all_locations:
                    boundaries["closing"][dst] -= qty
            lines.append(line)
        return {"balances": boundaries, "lines": lines}

    @api.model
    def _valuation_context(self, params, boundary):
        at_date = boundary - timedelta(microseconds=1)
        return {
            "to_date": at_date, "at_date": at_date,
            "location": list(params["all_locations"]),
            "owners": [False, params["company"].partner_id.id],
            "strict": True, "allowed_company_ids": [params["company"].id],
            "active_test": False,
        }

    @api.model
    def _endpoint(self, params, collected, name):
        """Allocate the standard company value to valued locations and lots."""
        balances = collected["balances"][name]
        by_product = defaultdict(float)
        by_lot = defaultdict(float)
        for (product_id, lot_id, _location_id), quantity in balances.items():
            by_product[product_id] += quantity
            by_lot[(product_id, lot_id)] += quantity
        context = self._valuation_context(params, params["start" if name == "opening" else "end"])
        valued_products = params["products"].with_context(context)
        product_qty = {product.id: product.qty_available for product in valued_products}
        product_value = {product.id: product.total_value for product in valued_products}
        lot_ids = {lot_id for (_product_id, lot_id) in by_lot if lot_id}
        lots = self.env["stock.lot"].browse(list(lot_ids)).with_context(context)
        lot_basis = {lot.id: (lot.product_qty, lot.total_value) for lot in lots}
        values = {}
        diagnostics = defaultdict(list)
        boundary = params["start" if name == "opening" else "end"]
        historical = boundary < params["cutoff"]
        manual_ids = set()
        valued_ids = set()
        if historical and params["products"]:
            manual_ids = set(self.env["product.value"].search([
                ("company_id", "=", params["company"].id),
                ("product_id", "in", params["products"].ids),
                ("move_id", "=", False),
                ("date", "<", boundary),
            ]).mapped("product_id").ids)
            valued_ids = set(self.env["stock.move"].search([
                ("company_id", "=", params["company"].id),
                ("product_id", "in", params["products"].ids),
                ("state", "=", "done"), ("date", "<", boundary),
                "|", ("is_in", "=", True), ("is_out", "=", True),
            ]).mapped("product_id").ids)
        for key, quantity in balances.items():
            product_id, lot_id, _location_id = key
            product = params["products"].browse(product_id)
            if historical and not product.uom_id.is_zero(quantity) and (
                    (product.cost_method == "standard" and
                     (product.lot_valuated or product_id not in manual_ids)) or
                    (product.cost_method != "standard" and product_id not in valued_ids)):
                values[key] = None
                diagnostics[product_id].append("missing_historical_basis")
                continue
            if product.lot_valuated:
                basis = lot_basis.get(lot_id)
                denominator = by_lot[(product_id, lot_id)]
                if not basis or product.uom_id.is_zero(denominator) or product.uom_id.is_zero(basis[0]):
                    values[key] = None if not product.uom_id.is_zero(quantity) else 0.0
                    if values[key] is None:
                        diagnostics[product_id].append("missing_lot_valuation_basis")
                    continue
                value = basis[1] * quantity / basis[0]
            else:
                denominator = by_product[product_id]
                standard_qty = product_qty[product_id]
                if product.uom_id.is_zero(denominator) or product.uom_id.is_zero(standard_qty):
                    values[key] = None if not product.uom_id.is_zero(quantity) else 0.0
                    if values[key] is None:
                        diagnostics[product_id].append("missing_company_valuation_basis")
                    continue
                value = product_value[product_id] * quantity / standard_qty
            values[key] = value
        for product in params["products"]:
            if not product.uom_id.is_zero(by_product[product.id] - product_qty[product.id]):
                diagnostics[product.id].append("standard_quantity_mismatch")
        return values, diagnostics
    @api.model
    def _operation(self, line, all_locations):
        move = line.move_id
        src = line.location_id
        dst = line.location_dest_id
        picking = move.picking_id
        if picking and "historical_pos_order_id" in picking._fields and picking.historical_pos_order_id:
            return "historical_writeoff"
        if move.scrap_id:
            return "scrap"
        if src.id in all_locations and dst.id in all_locations:
            return "internal_transfer"
        if src.usage == "customer" and dst.id in all_locations:
            return "customer_return"
        if dst.usage == "supplier" and src.id in all_locations:
            return "supplier_return"
        if src.usage == "inventory" and dst.id in all_locations:
            return "inventory_gain"
        if dst.usage == "inventory" and src.id in all_locations:
            return "inventory_loss"
        if dst.usage == "customer" and picking and (picking.pos_order_id or picking.pos_session_id):
            return "pos_sale"
        if dst.usage == "customer" and move.sale_line_id:
            return "sale_delivery"
        if src.usage == "supplier" and dst.id in all_locations:
            return "supplier_receipt"
        return "other"

    @api.model
    def _movement_amounts(self, params, collected):
        """Use recorded external values and a single pre-event internal basis."""
        company = params["company"]
        all_locations = params["all_locations"]
        by_move = defaultdict(list)
        for line in collected["lines"]:
            by_move[line.move_id.id].append(line)
        amounts = {}
        diagnostics = defaultdict(list)
        for move_lines in by_move.values():
            move = move_lines[0].move_id
            external = [line for line in move_lines if
                        (line.location_id.id in all_locations) != (line.location_dest_id.id in all_locations)]
            denominator = sum(line.quantity_product_uom for line in external)
            if external:
                if not denominator:
                    diagnostics[move.product_id.id].append("zero_movement_denominator")
                    for line in external:
                        amounts[line.id] = None
                else:
                    remainder = company.currency_id.round(move.value)
                    ordered = sorted(external, key=lambda line: line.id)
                    for line in ordered[:-1]:
                        share = company.currency_id.round(move.value * line.quantity_product_uom / denominator)
                        amounts[line.id] = share
                        remainder -= share
                    amounts[ordered[-1].id] = company.currency_id.round(remainder)
        valuation_events = defaultdict(set)
        for line in collected["lines"]:
            if ((line.location_id.id in all_locations) !=
                    (line.location_dest_id.id in all_locations)):
                valuation_events[line.product_id.id].add(line.move_id.date)
        for value in self.env["product.value"].search_fetch([
            ("company_id", "=", company.id),
            ("product_id", "in", params["products"].ids),
            ("date", "<=", params["cutoff"]),
        ], ["product_id", "date"]):
            valuation_events[value.product_id.id].add(value.date)
        valuation_events = {product_id: sorted(dates) for product_id, dates in valuation_events.items()}
        internal_lines = []
        boundaries = {}
        for line in collected["lines"]:
            if line.id in amounts or not params["start"] <= line.move_id.date < params["end"]:
                continue
            if line.location_id.id not in all_locations or line.location_dest_id.id not in all_locations:
                continue
            product = line.product_id
            lot_id = line.lot_id.id or 0
            events = valuation_events.get(product.id, ())
            epoch = bisect_left(events, line.move_id.date)
            cache_key = (product.id, lot_id if product.lot_valuated else 0, epoch)
            # A company's basis does not change between external valuation events.
            # Use the event just before this interval to batch products sharing it.
            boundary = (events[epoch - 1] + timedelta(microseconds=1)
                        if epoch else line.move_id.date)
            boundaries[cache_key] = min(boundaries.get(cache_key, boundary), boundary)
            internal_lines.append((line, cache_key))
        keys_by_boundary = defaultdict(list)
        for cache_key, boundary in boundaries.items():
            keys_by_boundary[boundary].append(cache_key)
        internal_cost = {}
        for boundary, cache_keys in keys_by_boundary.items():
            context = self._valuation_context(params, boundary)
            product_ids = sorted({product_id for product_id, lot_id, _epoch in cache_keys if not lot_id})
            lot_ids = sorted({lot_id for _product_id, lot_id, _epoch in cache_keys if lot_id})
            basis = {}
            if product_ids:
                products = self.env["product.product"].browse(product_ids).with_context(context)
                quantities = products.mapped("qty_available")
                values = products.mapped("total_value")
                basis.update({(product.id, 0): (quantity, value)
                              for product, quantity, value in zip(products, quantities, values)})
            if lot_ids:
                lots = self.env["stock.lot"].browse(lot_ids).with_context(context)
                quantities = lots.mapped("product_qty")
                values = lots.mapped("total_value")
                basis.update({(lot.product_id.id, lot.id): (quantity, value)
                              for lot, quantity, value in zip(lots, quantities, values)})
            relevant_products = {product_id for product_id, _lot_id, _epoch in cache_keys}
            manual_ids = set(self.env["product.value"].search([
                ("company_id", "=", company.id),
                ("product_id", "in", list(relevant_products)),
                ("move_id", "=", False), ("date", "<", boundary),
            ]).mapped("product_id").ids)
            valued_ids = set(self.env["stock.move"].search([
                ("company_id", "=", company.id),
                ("product_id", "in", list(relevant_products)),
                ("state", "=", "done"), ("date", "<", boundary),
                "|", ("is_in", "=", True), ("is_out", "=", True),
            ]).mapped("product_id").ids)
            for cache_key in cache_keys:
                product_id, lot_id, _epoch = cache_key
                product = params["products"].browse(product_id)
                quantity, value = basis.get((product_id, lot_id), (0.0, 0.0))
                supported = not product.uom_id.is_zero(quantity)
                if supported and boundary < params["cutoff"]:
                    if product.cost_method == "standard":
                        supported = not product.lot_valuated and product_id in manual_ids
                    else:
                        supported = product_id in valued_ids
                internal_cost[cache_key] = value / quantity if supported else None
        for line, cache_key in internal_lines:
            unit_cost = internal_cost[cache_key]
            amounts[line.id] = (None if unit_cost is None else
                                company.currency_id.round(line.quantity_product_uom * unit_cost))
            if unit_cost is None:
                diagnostics[line.product_id.id].append("missing_internal_valuation_basis")
        return amounts, diagnostics
