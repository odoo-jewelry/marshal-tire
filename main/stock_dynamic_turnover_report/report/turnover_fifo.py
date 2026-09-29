"""Reconstruct company FIFO receipts and their movement shares."""

from collections import defaultdict
from datetime import timedelta
import json

from odoo import api, fields, models


class StockDynamicTurnoverFifo(models.AbstractModel):
    _inherit = "stock.dynamic.turnover.report"

    @api.model
    def _fifo_stack(self, params, product, boundary, lot=None):
        context = self._valuation_context(params, boundary)
        valued_product = product.with_context(context)
        valued_lot = lot.with_context(context) if lot else None
        stack, first_qty = valued_product._run_fifo_get_stack(
            lot=valued_lot, at_date=boundary - timedelta(microseconds=1))
        result = []
        for index, move in enumerate(stack):
            qty = first_qty if index == 0 else move._get_valued_qty(lot=valued_lot)
            if product.uom_id.compare(qty, 0) > 0:
                result.append((move, lot.id if lot else 0, qty))
        return result

    @api.model
    def _receipt_leaves(self, params, collected):
        """Reconstruct company FIFO receipt attribution without mutating stock."""
        company = params["company"]
        currency = company.currency_id
        leaves = {}
        diagnostics = []
        by_product = defaultdict(list)
        for line in collected["lines"]:
            if line.move_id.is_in or line.move_id.is_out:
                by_product[line.product_id.id].append(line)
        for product in params["products"]:
            product_lines = by_product[product.id]
            if not product_lines and not any(key[0] == product.id for key in collected["balances"]["opening"]):
                continue
            lot_ids = {line.lot_id.id for line in product_lines if line.lot_id}
            lot_ids |= {key[1] for key in collected["balances"]["opening"] if key[0] == product.id and key[1]}
            lot_ids |= {key[1] for key in collected["balances"]["closing"] if key[0] == product.id and key[1]}
            lots = [self.env["stock.lot"].browse(lot_id) for lot_id in sorted(lot_ids)] if product.lot_valuated else [None]
            if product.cost_method != "fifo":
                leaves[(product.id, -1)] = self._unattributed_receipt(
                    params, collected, product, "not_applicable")
                continue
            if product.lot_valuated and (not lot_ids or any(
                    not line.lot_id and (line.move_id.is_in or line.move_id.is_out)
                    for line in product_lines)):
                diagnostics.append({"product_id": product.id, "code": "missing_valuation_lot"})
                leaves[(product.id, 0)] = self._unattributed_receipt(
                    params, collected, product, "missing_valuation_lot")
                continue
            opening = defaultdict(float)
            closing = defaultdict(float)
            receipt_moves = {}
            for lot in lots:
                for move, lot_id, qty in self._fifo_stack(params, product, params["start"], lot):
                    opening[(move.id, lot_id)] += qty
                    receipt_moves[move.id] = move
                for move, lot_id, qty in self._fifo_stack(params, product, params["end"], lot):
                    closing[(move.id, lot_id)] += qty
                    receipt_moves[move.id] = move
            opening_company_qty = sum(
                qty for (pid, _lot_id, _location_id), qty in collected["balances"]["opening"].items()
                if pid == product.id)
            closing_company_qty = sum(
                qty for (pid, _lot_id, _location_id), qty in collected["balances"]["closing"].items()
                if pid == product.id)
            if (not product.uom_id.is_zero(opening_company_qty - sum(opening.values())) or
                    not product.uom_id.is_zero(closing_company_qty - sum(closing.values()))):
                diagnostics.append({"product_id": product.id, "code": "fifo_stack_quantity_mismatch"})
                leaves[(product.id, 0)] = self._unattributed_receipt(
                    params, collected, product, "fifo_stack_quantity_mismatch")
                continue
            incoming = defaultdict(float)
            consumed = defaultdict(float)
            spent_value = defaultdict(float)
            events = defaultdict(list)
            valued_moves = {line.move_id.id: line.move_id for line in product_lines}
            period_moves = sorted(
                (move for move in valued_moves.values()
                 if params["start"] <= move.date < params["end"]),
                key=lambda move: (move.date, move.id),
            )
            failure = None
            for move in period_moves:
                if not move.is_in:
                    continue
                parts = [(lot.id if lot else 0, move._get_valued_qty(lot=lot)) for lot in lots]
                parts = [(lot_id, qty) for lot_id, qty in parts if not product.uom_id.is_zero(qty)]
                total_qty = sum(qty for _lot_id, qty in parts)
                remaining_value = currency.round(move.value)
                for index, (lot_id, qty) in enumerate(parts):
                    key = (move.id, lot_id)
                    incoming[key] += qty
                    receipt_moves[move.id] = move
                    amount = (currency.round(move.value * qty / total_qty)
                              if index < len(parts) - 1 else currency.round(remaining_value))
                    remaining_value -= amount
                    events[key].append(self._receipt_event(move, qty, amount, "incoming", product_lines, params))
            by_time_lot = defaultdict(list)
            for move in period_moves:
                if not move.is_out:
                    continue
                for lot in lots:
                    qty = move._get_valued_qty(lot=lot)
                    if not product.uom_id.is_zero(qty):
                        by_time_lot[(move.date, lot.id if lot else 0)].append((move, qty, lot))
            # Split one recorded move value over its valued lots only once.
            move_lot_parts = defaultdict(list)
            for (_date, lot_id), outgoing in by_time_lot.items():
                for move, qty, _lot in outgoing:
                    move_lot_parts[move.id].append((lot_id, qty))
            move_lot_value = {}
            for move_id, parts in move_lot_parts.items():
                move = valued_moves[move_id]
                total_qty = sum(qty for _lot_id, qty in parts)
                remaining_value = currency.round(move.value)
                for index, (lot_id, qty) in enumerate(sorted(parts)):
                    value = (currency.round(move.value * qty / total_qty)
                             if index < len(parts) - 1 else currency.round(remaining_value))
                    move_lot_value[(move_id, lot_id)] = value
                    remaining_value -= value
            incoming_times = {
                (move.date, lot.id if lot else 0)
                for move in period_moves if move.is_in for lot in lots
                if not product.uom_id.is_zero(move._get_valued_qty(lot=lot))
            }
            for (move_date, lot_id), outgoing in sorted(by_time_lot.items()):
                if (move_date, lot_id) in incoming_times:
                    failure = "ambiguous_same_time"
                    break
                lot = outgoing[0][2]
                stack = [[move, remaining] for move, _lid, remaining in
                         self._fifo_stack(params, product, move_date, lot)]
                for move, qty, _lot in sorted(outgoing, key=lambda entry: entry[0].id):
                    remaining = qty
                    shares = []
                    while product.uom_id.compare(remaining, 0) > 0 and stack:
                        receipt, available = stack[0]
                        share = min(remaining, available)
                        shares.append((receipt, share))
                        remaining -= share
                        stack[0][1] -= share
                        if product.uom_id.is_zero(stack[0][1]):
                            stack.pop(0)
                    if product.uom_id.compare(remaining, 0) > 0:
                        failure = "insufficient_fifo_history"
                        break
                    weights = []
                    for receipt, share in shares:
                        valued_qty = receipt._get_valued_qty()
                        if product.uom_id.is_zero(valued_qty):
                            failure = "zero_receipt_denominator"
                            break
                        weights.append(share * receipt.value / valued_qty)
                    if failure:
                        break
                    if any(weight < 0 for weight in weights) and any(weight > 0 for weight in weights):
                        failure = "mixed_negative_fifo_basis"
                        break
                    total_weight = sum(weights)
                    if total_weight < 0:
                        failure = "negative_fifo_basis"
                        break
                    if not total_weight:
                        weights = [share for _receipt, share in shares]
                        total_weight = sum(weights)
                        diagnostics.append({"product_id": product.id, "code": "zero_cost_fifo_basis", "move_id": move.id})
                    lot_value = move_lot_value[(move.id, lot_id)]
                    remaining_value = lot_value
                    for index, (receipt, share) in enumerate(shares):
                        key = (receipt.id, lot_id)
                        receipt_moves[receipt.id] = receipt
                        value = (currency.round(lot_value * weights[index] / total_weight)
                                 if index < len(shares) - 1 else currency.round(remaining_value))
                        remaining_value -= value
                        consumed[key] += share
                        spent_value[key] += value
                        events[key].append(self._receipt_event(move, -share, -value, "outgoing", product_lines, params))
                if failure:
                    break
            all_keys = opening.keys() | closing.keys() | incoming.keys() | consumed.keys()
            if not failure:
                for key in all_keys:
                    if not product.uom_id.is_zero(opening[key] + incoming[key] - consumed[key] - closing[key]):
                        failure = "fifo_reconciliation"
                        break
            if failure:
                diagnostics.append({"product_id": product.id, "code": failure})
                leaves[(product.id, 0)] = self._unattributed_receipt(params, collected, product, failure)
                continue
            for move_id, _lot_id in all_keys:
                move = receipt_moves[move_id]
                valued_qty = move._get_valued_qty()
                if product.uom_id.is_zero(valued_qty):
                    failure = "zero_receipt_denominator"
                    break
            if failure:
                diagnostics.append({"product_id": product.id, "code": failure})
                leaves[(product.id, 0)] = self._unattributed_receipt(params, collected, product, failure)
                continue
            by_receipt = defaultdict(lambda: {
                "opening_qty": 0.0, "closing_qty": 0.0, "incoming_qty": 0.0,
                "outgoing_qty": 0.0, "opening_value": 0.0, "closing_value": 0.0,
                "incoming_value": 0.0, "outgoing_value": 0.0, "events": [],
            })
            for key in all_keys:
                move_id, _lot_id = key
                move = receipt_moves[move_id]
                unit_cost = move.value / move._get_valued_qty()
                entry = by_receipt[move_id]
                entry["opening_qty"] += opening[key]
                entry["closing_qty"] += closing[key]
                entry["incoming_qty"] += incoming[key]
                entry["outgoing_qty"] += consumed[key]
                entry["opening_value"] += opening[key] * unit_cost
                entry["closing_value"] += closing[key] * unit_cost
                entry["incoming_value"] += incoming[key] * unit_cost
                entry["outgoing_value"] += spent_value[key]
                entry["events"].extend(events[key])
            for boundary_name in ("opening", "closing"):
                context = self._valuation_context(
                    params, params["start" if boundary_name == "opening" else "end"])
                standard_value = product.with_context(context).total_value
                receipt_value = sum(
                    entry[boundary_name + "_value"] for entry in by_receipt.values())
                if not currency.is_zero(standard_value - receipt_value):
                    diagnostics.append({
                        "product_id": product.id,
                        "code": "receipt_value_vs_standard",
                        "boundary": boundary_name,
                        "difference": currency.round(standard_value - receipt_value),
                    })
            for move_id, entry in by_receipt.items():
                move = receipt_moves[move_id]
                purchase_line = move.purchase_line_id
                order = (purchase_line.order_id if purchase_line and purchase_line.has_access("read")
                         else self.env["purchase.order"])
                order_id = order.id if order and order.has_access("read") else 0
                entry.update({
                    "product_id": product.id, "receipt_id": move_id, "purchase_order_id": order_id,
                    "label": self._receipt_label(move, order if order_id else None),
                    "diagnostics": [],
                })
                leaves[(product.id, move_id)] = entry
        return leaves, diagnostics

    @api.model
    def _receipt_label(self, move, order):
        qty = move._get_valued_qty()
        price = move.value / qty if qty else 0.0
        source = order.name if order else "%s (%s)" % (
            move.picking_id.name if move.picking_id else move.reference or self.env._("Receipt %s") % move.id,
            self.env._("No PO"),
        )
        return "%s · %s · %s" % (fields.Datetime.to_string(move.date), source, price)

    @api.model
    def _receipt_event(self, move, qty, value, direction, lines, params):
        line = next((item for item in lines if item.move_id == move), None)
        return {
            "move_id": move.id, "date": fields.Datetime.to_string(move.date),
            "quantity": qty, "amount": value, "direction": direction,
            "operation": self._operation(line, params["all_locations"]) if line else "other",
            "document_model": "stock.move", "document_id": move.id,
        }

    @api.model
    def _unattributed_receipt(self, params, collected, product, reason):
        opening = sum(qty for (pid, _lot, _location), qty in collected["balances"]["opening"].items() if pid == product.id)
        closing = sum(qty for (pid, _lot, _location), qty in collected["balances"]["closing"].items() if pid == product.id)
        incoming = outgoing = incoming_value = outgoing_value = 0.0
        events = []
        seen = set()
        for line in collected["lines"]:
            move = line.move_id
            if line.product_id != product or not params["start"] <= move.date < params["end"] or move.id in seen:
                continue
            seen.add(move.id)
            qty = move._get_valued_qty()
            if move.is_in:
                incoming += qty
                incoming_value += move.value
                events.append(self._receipt_event(move, qty, move.value, "incoming", collected["lines"], params))
            elif move.is_out:
                outgoing += qty
                outgoing_value += move.value
                events.append(self._receipt_event(move, -qty, -move.value, "outgoing", collected["lines"], params))
        context_open = self._valuation_context(params, params["start"])
        context_close = self._valuation_context(params, params["end"])
        return {
            "product_id": product.id, "receipt_id": 0 if reason != "not_applicable" else -1,
            "purchase_order_id": 0, "label": self.env._("Not attributed to receipts") if reason != "not_applicable" else self.env._("FIFO is not applicable"),
            "opening_qty": opening, "closing_qty": closing,
            "incoming_qty": incoming, "outgoing_qty": outgoing,
            "opening_value": product.with_context(context_open).total_value,
            "closing_value": product.with_context(context_close).total_value,
            "incoming_value": incoming_value, "outgoing_value": outgoing_value,
            "diagnostics": [reason], "events": events,
        }
    @api.model
    def _receipt_tree(self, params, leaves, diagnostics):
        dimensions = params["dimensions"]
        product_map = {product.id: product for product in params["products"]}
        receipt_labels = {leaf["receipt_id"]: leaf["label"] for leaf in leaves.values()}
        filters = params["ids"]
        selected = []
        incomplete_filter = False
        for leaf in leaves.values():
            if filters["receipt_ids"] and leaf["receipt_id"] not in filters["receipt_ids"]:
                if leaf["receipt_id"] <= 0:
                    incomplete_filter = True
                continue
            if filters["purchase_order_ids"] and leaf["purchase_order_id"] not in filters["purchase_order_ids"]:
                if leaf["receipt_id"] <= 0:
                    incomplete_filter = True
                continue
            selected.append(leaf)
        if incomplete_filter:
            diagnostics.append({"code": "filtered_attribution_incomplete"})
        nodes = {}

        def ensure(path):
            key = json.dumps(path, separators=(",", ":"))
            if key not in nodes:
                nodes[key] = {
                    "key": key, "path": path, "level": len(path),
                    "opening_qty": defaultdict(float), "closing_qty": defaultdict(float),
                    "incoming_qty": defaultdict(float), "outgoing_qty": defaultdict(float),
                    "opening_value": 0.0, "closing_value": 0.0,
                    "incoming_value": 0.0, "outgoing_value": 0.0,
                    "operations": defaultdict(lambda: {"qty": defaultdict(float), "value": 0.0}),
                    "diagnostics": set(), "events": [],
                }
            return nodes[key]

        ensure(())
        for leaf in selected:
            product = product_map[leaf["product_id"]]
            values = {
                "receipt": leaf["receipt_id"], "product": product.id,
                "category": product.categ_id.id,
            }
            path = tuple((dimension, values[dimension]) for dimension in dimensions)
            for index in range(len(path) + 1):
                node = ensure(path[:index])
                for name in ("opening", "closing", "incoming", "outgoing"):
                    node[name + "_qty"][product.uom_id.id] += leaf[name + "_qty"]
                    amount = leaf[name + "_value"]
                    if node[name + "_value"] is not None:
                        node[name + "_value"] = None if amount is None else node[name + "_value"] + amount
                for event in leaf["events"]:
                    op = node["operations"][event["operation"]]
                    op["qty"][product.uom_id.id] += event["quantity"]
                    if op["value"] is not None:
                        op["value"] = None if event["amount"] is None else op["value"] + event["amount"]
                node["events"].extend(leaf["events"])
                node["diagnostics"].update(leaf["diagnostics"])

        def label(path):
            if not path:
                return self.env._("Total")
            dimension, record_id = path[-1]
            if dimension == "receipt":
                return receipt_labels[record_id]
            model_name = "product.product" if dimension == "product" else "product.category"
            return self.env[model_name].browse(record_id).display_name

        currency = params["company"].currency_id
        rows = []
        for node in sorted(nodes.values(), key=lambda item: item["path"]):
            monetary = {}
            for name in ("opening", "closing", "incoming", "outgoing"):
                value = node[name + "_value"]
                monetary[name + "_value"] = None if value is None else currency.round(value)
            values = tuple(monetary[name + "_value"] for name in ("opening", "closing", "incoming", "outgoing"))
            delta = None if None in values else currency.round(
                monetary["closing_value"] - monetary["opening_value"]
                - monetary["incoming_value"] + monetary["outgoing_value"])
            rows.append({
                "key": node["key"],
                "parent_key": json.dumps(node["path"][:-1], separators=(",", ":")) if node["path"] else None,
                "label": label(node["path"]), "level": node["level"], "path": node["path"],
                "measures": {
                    **monetary, "valuation_delta": delta,
                    **{name + "_qty": dict(node[name + "_qty"]) for name in ("opening", "closing", "incoming", "outgoing")},
                },
                "operations": {
                    operation: {"quantity": dict(value["qty"]),
                                "value": None if value["value"] is None else currency.round(value["value"])}
                    for operation, value in node["operations"].items()
                },
                "diagnostics": sorted(node["diagnostics"]), "events": node["events"],
            })
        return rows
