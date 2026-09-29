"""Read-only stock turnover report integrated with Dynamic Financial Reports."""

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json

import pytz

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError


SPATIAL_DIMENSIONS = ("warehouse", "location", "product", "category")
RECEIPT_DIMENSIONS = ("receipt", "product", "category")
OPERATIONS = (
    "historical_writeoff", "scrap", "internal_transfer", "customer_return",
    "supplier_return", "inventory_gain", "inventory_loss", "pos_sale",
    "sale_delivery", "supplier_receipt", "other",
)
CONTEXT_KEYS = (
    "location", "warehouse", "warehouse_id", "owners", "owner_id", "lot_id",
    "package_id", "to_date", "from_date", "at_date", "fifo_qty_already_processed",
    "pos_historical_fifo_date", "strict",
)


class StockDynamicTurnoverReport(models.AbstractModel):
    _name = "stock.dynamic.turnover.report"
    _description = "Dynamic Stock Turnover Report"

    @api.model
    def _normalize(self, options):
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(self.env._("Inventory manager access is required."))
        if not isinstance(options, dict):
            raise UserError(self.env._("Invalid report options."))
        allowed = {
            "company_id", "date_from", "date_to", "mode", "row_dimensions",
            "columns", "product_ids", "category_ids", "warehouse_ids",
            "location_ids", "receipt_ids", "purchase_order_ids", "include_children",
            "page", "page_size", "cutoff",
        }
        if set(options) - allowed:
            raise UserError(self.env._("Unknown report option."))
        company_id = options.get("company_id") or self.env.company.id
        if type(company_id) is not int or company_id not in self.env.user.company_ids.ids:
            raise AccessError(self.env._("The selected company is unavailable."))
        company = self.env["res.company"].browse(company_id)
        company.check_access("read")
        context = {key: value for key, value in self.env.context.items() if key not in CONTEXT_KEYS}
        context.update(allowed_company_ids=[company.id], active_test=False)
        service = self.with_company(company).with_context(context)
        return service._normalize_scoped(options, company)

    @api.model
    def _normalize_scoped(self, options, company):
        mode = options.get("mode", "stock")
        if mode not in ("stock", "receipts"):
            raise UserError(self.env._("Invalid report mode."))
        dimensions = options.get("row_dimensions", ["product"])
        permitted = SPATIAL_DIMENSIONS if mode == "stock" else RECEIPT_DIMENSIONS
        if (not isinstance(dimensions, list) or any(value not in permitted for value in dimensions)
                or len(set(dimensions)) != len(dimensions)):
            raise UserError(self.env._("Invalid row dimensions."))
        columns = options.get("columns", "turnover")
        if columns not in ("turnover", "operations"):
            raise UserError(self.env._("Invalid report columns."))
        include_children = options.get("include_children", True)
        if type(include_children) is not bool:
            raise UserError(self.env._("Invalid location filter."))

        def selected_ids(key):
            value = options.get(key, [])
            if not isinstance(value, list) or any(type(item) is not int or item <= 0 for item in value):
                raise UserError(self.env._("Invalid report selection."))
            return sorted(set(value))

        ids = {key: selected_ids(key) for key in (
            "product_ids", "category_ids", "warehouse_ids", "location_ids",
            "receipt_ids", "purchase_order_ids",
        )}
        if mode == "stock" and (ids["receipt_ids"] or ids["purchase_order_ids"]):
            raise UserError(self.env._("Receipt filters require receipt mode."))
        if mode == "receipts" and (ids["warehouse_ids"] or ids["location_ids"]):
            raise UserError(self.env._("Spatial filters are unavailable in receipt mode."))
        try:
            tz = pytz.timezone(self.env.user.tz or "UTC")
        except pytz.UnknownTimeZoneError:
            raise UserError(self.env._("Invalid user time zone."))
        today = datetime.now(tz).date()

        def day(key, default):
            value = options.get(key)
            if not value:
                return default
            try:
                if isinstance(value, datetime):
                    raise ValueError
                return value if isinstance(value, date) else date.fromisoformat(value)
            except (TypeError, ValueError):
                raise UserError(self.env._("Invalid report date."))

        first = day("date_from", today.replace(day=1))
        last = day("date_to", today)
        if first > last or last > today:
            raise UserError(self.env._("Invalid report period."))
        try:
            start = tz.localize(datetime.combine(first, time.min), is_dst=None).astimezone(timezone.utc).replace(tzinfo=None)
            end = tz.localize(datetime.combine(last + timedelta(days=1), time.min), is_dst=None).astimezone(timezone.utc).replace(tzinfo=None)
        except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
            raise UserError(self.env._("Ambiguous local day boundary."))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = options.get("cutoff")
        if cutoff:
            try:
                cutoff = datetime.fromisoformat(cutoff)
            except (TypeError, ValueError):
                raise UserError(self.env._("Invalid report cutoff."))
            if cutoff.tzinfo or cutoff > now or cutoff < start:
                raise UserError(self.env._("Invalid report cutoff."))
        else:
            cutoff = now
        end = min(end, cutoff + timedelta(microseconds=1))
        page = options.get("page", 1)
        size = options.get("page_size", 50)
        if type(page) is not int or page < 1 or type(size) is not int or not 1 <= size <= 200:
            raise UserError(self.env._("Invalid report page."))

        domain = ["|", ("company_id", "=", False), ("company_id", "=", company.id)]
        models = {
            "product_ids": ("product.product", domain),
            "category_ids": ("product.category", []),
            "warehouse_ids": ("stock.warehouse", [("company_id", "=", company.id)]),
            "location_ids": ("stock.location", [("company_id", "=", company.id)]),
            "receipt_ids": ("stock.move", [("company_id", "=", company.id), ("state", "=", "done"), ("is_in", "=", True)]),
            "purchase_order_ids": ("purchase.order", [("company_id", "=", company.id)]),
        }
        selections = {}
        for key, (model_name, scope) in models.items():
            Model = self.env[model_name].with_context(active_test=False)
            if ids[key]:
                Model.check_access("read")
            records = Model.search(scope + [("id", "in", ids[key])]) if ids[key] else Model.browse()
            if len(records) != len(ids[key]):
                raise AccessError(self.env._("A selected record is unavailable."))
            selections[key] = records
        if any(not product.is_storable for product in selections["product_ids"]):
            raise UserError(self.env._("Only tracked stock products are supported."))

        Product = self.env["product.product"].with_context(active_test=False)
        product_domain = [("is_storable", "=", True)] + domain
        if ids["product_ids"]:
            product_domain.append(("id", "in", ids["product_ids"]))
        if ids["category_ids"]:
            product_domain.append(("categ_id", "child_of", ids["category_ids"]))
        products = Product.search(product_domain)
        locations = self.env["stock.location"].with_context(active_test=False).search([
            ("company_id", "=", company.id), ("usage", "in", ("internal", "transit")),
        ])
        all_locations = set(locations.ids)
        scope_locations = set(all_locations)
        if ids["warehouse_ids"]:
            views = selections["warehouse_ids"].mapped("view_location_id").ids
            scope_locations &= set(self.env["stock.location"].search([("id", "child_of", views)]).ids)
        if ids["location_ids"]:
            location_domain = [("id", "child_of", ids["location_ids"])] if include_children else [("id", "in", ids["location_ids"])]
            scope_locations &= set(self.env["stock.location"].search(location_domain).ids)
            if ids["warehouse_ids"] and not set(ids["location_ids"]) <= set(
                    self.env["stock.location"].search([("id", "child_of", views)]).ids):
                raise UserError(self.env._("A selected location is outside its warehouse."))
        self._check_sources(company, products, product_domain, all_locations)
        return {
            "service": self, "company": company, "mode": mode, "dimensions": dimensions,
            "columns": columns, "date_from": first, "date_to": last, "start": start,
            "end": end, "cutoff": cutoff, "page": page, "page_size": size,
            "ids": ids, "selections": selections, "products": products,
            "locations": locations, "all_locations": all_locations,
            "scope_locations": scope_locations,
        }

    @api.model
    def _check_sources(self, company, products, product_domain, all_locations):
        denied = self.env._("The stock history is not fully accessible.")
        Product = self.env["product.product"].with_context(active_test=False)
        if Product.search_count(product_domain) != Product.sudo().search_count(product_domain):
            raise AccessError(denied)
        if not products:
            return
        domains = {
            "stock.location": [("id", "in", list(all_locations))],
            "stock.quant": [("company_id", "=", company.id), ("product_id", "in", products.ids), ("location_id", "in", list(all_locations))],
            "stock.move": [("company_id", "=", company.id), ("product_id", "in", products.ids), ("state", "=", "done")],
            "stock.move.line": [("company_id", "=", company.id), ("product_id", "in", products.ids), ("move_id.state", "=", "done")],
            "stock.lot": [("company_id", "=", company.id), ("product_id", "in", products.ids)],
            "product.value": [("company_id", "=", company.id), ("product_id", "in", products.ids)],
        }
        for model_name, source_domain in domains.items():
            Model = self.env[model_name].with_context(active_test=False)
            Model.check_access("read")
            if Model.search_count(source_domain) != Model.sudo().search_count(source_domain):
                raise AccessError(denied)
    @api.model
    def _stock_tree(self, params, collected, opening_values, closing_values, amounts, diagnostics):
        dimensions = params["dimensions"]
        scope = params["scope_locations"]
        locations = {location.id: location for location in params["locations"]}
        products = {product.id: product for product in params["products"]}
        nodes = {}

        def descriptor(product_id, location_id):
            product = products[product_id]
            location = locations[location_id]
            values = {
                "warehouse": location.warehouse_id.id or 0,
                "location": location_id,
                "product": product_id,
                "category": product.categ_id.id,
            }
            return tuple((dimension, values[dimension]) for dimension in dimensions)

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

        def paths(product_id, location_id):
            full = descriptor(product_id, location_id)
            return [ensure(full[:index]) for index in range(len(full) + 1)]

        def add_value(node, name, value):
            if node[name] is not None:
                node[name] = None if value is None else node[name] + value

        ensure(())
        for name, values in (("opening", opening_values), ("closing", closing_values)):
            for (product_id, _lot_id, location_id), quantity in collected["balances"][name].items():
                if location_id not in scope or not quantity:
                    continue
                product = products[product_id]
                for node in paths(product_id, location_id):
                    node[name + "_qty"][product.uom_id.id] += quantity
                    add_value(node, name + "_value", values.get((product_id, _lot_id, location_id)))
                    node["diagnostics"].update(diagnostics.get(product_id, ()))

        for line in collected["lines"]:
            move = line.move_id
            if not params["start"] <= move.date < params["end"]:
                continue
            product = line.product_id
            qty = line.quantity_product_uom
            amount = amounts.get(line.id)
            source = line.location_id.id in scope
            destination = line.location_dest_id.id in scope
            if not source and not destination:
                continue
            src_nodes = {node["key"]: node for node in paths(product.id, line.location_id.id)} if source else {}
            dst_nodes = {node["key"]: node for node in paths(product.id, line.location_dest_id.id)} if destination else {}
            operation = self._operation(line, params["all_locations"])
            for key in src_nodes.keys() | dst_nodes.keys():
                node = src_nodes.get(key) or dst_nodes.get(key)
                sign = int(key in dst_nodes) - int(key in src_nodes)
                if sign:
                    section = "incoming" if sign > 0 else "outgoing"
                    node[section + "_qty"][product.uom_id.id] += qty
                    add_value(node, section + "_value", amount)
                if params["columns"] == "operations" and (key in src_nodes or key in dst_nodes):
                    op = node["operations"][operation]
                    op["qty"][product.uom_id.id] += sign * qty
                    if sign:
                        op["value"] = None if op["value"] is None or amount is None else op["value"] + sign * amount
                for side_sign, present in ((-1, key in src_nodes), (1, key in dst_nodes)):
                    if not present:
                        continue
                    node["events"].append({
                        "move_line_id": line.id, "move_id": move.id,
                        "date": fields.Datetime.to_string(move.date),
                        "operation": operation, "quantity": side_sign * qty,
                        "amount": None if amount is None else side_sign * amount,
                        "uom_id": product.uom_id.id,
                        "source_location_id": line.location_id.id,
                        "destination_location_id": line.location_dest_id.id,
                        "boundary": bool(sign),
                        "document_model": "stock.move",
                        "document_id": move.id,
                    })
                node["diagnostics"].update(diagnostics.get(product.id, ()))

        def label(path):
            if not path:
                return self.env._("Total")
            dimension, record_id = path[-1]
            if not record_id:
                return self.env._("Outside warehouse")
            model_name = {
                "warehouse": "stock.warehouse", "location": "stock.location",
                "product": "product.product", "category": "product.category",
            }[dimension]
            record = self.env[model_name].browse(record_id)
            return record.display_name

        currency = params["company"].currency_id
        output = []
        for key, node in sorted(nodes.items(), key=lambda item: item[1]["path"]):
            monetary = {}
            for name in ("opening", "closing", "incoming", "outgoing"):
                value = node[name + "_value"]
                monetary[name + "_value"] = None if value is None else currency.round(value)
            operand = tuple(monetary[name + "_value"] for name in ("opening", "closing", "incoming", "outgoing"))
            delta = None if None in operand else currency.round(
                monetary["closing_value"] - monetary["opening_value"]
                - monetary["incoming_value"] + monetary["outgoing_value"]
            )
            measures = {
                **monetary,
                "valuation_delta": delta,
                **{name + "_qty": dict(node[name + "_qty"]) for name in ("opening", "closing", "incoming", "outgoing")},
            }
            operations = {
                operation: {"quantity": dict(value["qty"]),
                            "value": None if value["value"] is None else currency.round(value["value"])}
                for operation, value in node["operations"].items()
            }
            output.append({
                "key": key, "parent_key": json.dumps(node["path"][:-1], separators=(",", ":")) if node["path"] else None,
                "label": label(node["path"]), "level": node["level"], "path": node["path"],
                "measures": measures, "operations": operations,
                "diagnostics": sorted(node["diagnostics"]), "events": node["events"],
            })
        return output
    @api.model
    def _calculate(self, options):
        params = self._normalize({} if options is None else options)
        service = params["service"]
        collected = service._collect(params)
        diagnostics = []
        if params["mode"] == "stock":
            opening, opening_diag = service._endpoint(params, collected, "opening")
            closing, closing_diag = service._endpoint(params, collected, "closing")
            amounts, amount_diag = service._movement_amounts(params, collected)
            product_diag = defaultdict(list)
            for group in (opening_diag, closing_diag, amount_diag):
                for product_id, values in group.items():
                    product_diag[product_id].extend(values)
            rows = service._stock_tree(params, collected, opening, closing, amounts, product_diag)
        else:
            leaves, diagnostics = service._receipt_leaves(params, collected)
            rows = service._receipt_tree(params, leaves, diagnostics)
        canonical = {
            "company_id": params["company"].id,
            "date_from": params["date_from"].isoformat(),
            "date_to": params["date_to"].isoformat(),
            "mode": params["mode"], "row_dimensions": params["dimensions"],
            "columns": params["columns"], "include_children": options.get("include_children", True) if options else True,
            **params["ids"],
            "cutoff": params["cutoff"].isoformat(timespec="microseconds"),
            "page": params["page"], "page_size": params["page_size"],
        }
        source_digest = hashlib.sha256()
        source_digest.update(json.dumps({key: value for key, value in canonical.items() if key not in ("page", "page_size")},
                                        sort_keys=True).encode())
        source_digest.update(json.dumps(rows, sort_keys=True, default=str).encode())
        source_digest.update(json.dumps(diagnostics, sort_keys=True, default=str).encode())
        if params["products"]:
            domains = (
                ("product.product", [("id", "in", params["products"].ids)],
                 ("id", "write_date", "categ_id", "uom_id", "standard_price", "cost_method", "lot_valuated", "is_storable", "active")),
                ("stock.quant", [("company_id", "=", params["company"].id), ("product_id", "in", params["products"].ids)],
                 ("id", "write_date", "quantity", "product_id", "lot_id", "location_id", "owner_id")),
                ("stock.move", [("company_id", "=", params["company"].id), ("product_id", "in", params["products"].ids), ("state", "=", "done")],
                 ("id", "write_date", "date", "value", "state", "is_in", "is_out", "picking_id", "sale_line_id", "purchase_line_id")),
                ("stock.move.line", [("company_id", "=", params["company"].id), ("product_id", "in", params["products"].ids), ("move_id.state", "=", "done")],
                 ("id", "write_date", "quantity_product_uom", "location_id", "location_dest_id", "lot_id", "owner_id")),
                ("product.value", [("company_id", "=", params["company"].id), ("product_id", "in", params["products"].ids)],
                 ("id", "write_date", "date", "value", "move_id", "lot_id")),
            )
            for model_name, domain, field_names in domains:
                Model = self.env[model_name].with_context(active_test=False)
                records = Model.search(domain, order="id")
                source_digest.update(model_name.encode())
                for start in range(0, len(records), 500):
                    values = records[start:start + 500].read(list(field_names), load=None)
                    source_digest.update(json.dumps(values, sort_keys=True, default=str).encode())
        revision = source_digest.hexdigest()
        return params, rows, diagnostics, canonical, revision

    @api.model
    def get_report(self, options=None):
        params, rows, diagnostics, canonical, revision = self._calculate({} if options is None else options)
        top_keys = [row["key"] for row in rows if row["level"] == 1]
        if top_keys:
            first = (params["page"] - 1) * params["page_size"]
            shown = set(top_keys[first:first + params["page_size"]])
            page_rows = [row for row in rows if row["level"] == 0 or
                         json.dumps(row["path"][:1], separators=(",", ":")) in shown]
        else:
            page_rows = rows
        page_rows = [{key: value for key, value in row.items() if key != "events"}
                     for row in page_rows]
        units = {product.uom_id.id: product.uom_id.name for product in params["products"]}
        totals = dict(rows[0]["measures"]) if rows else {}
        incomplete = any(totals.get(name + "_value") is None for name in (
            "opening", "closing", "incoming", "outgoing")) or any(
                item.get("code") not in ("receipt_value_vs_standard", "zero_cost_fifo_basis") for item in diagnostics)
        totals["incomplete"] = incomplete
        return {
            "options": canonical, "revision": revision,
            "cutoff": canonical["cutoff"], "mode": params["mode"],
            "columns": params["columns"], "row_dimensions": params["dimensions"],
            "currency": {"id": params["company"].currency_id.id, "name": params["company"].currency_id.name,
                         "symbol": params["company"].currency_id.symbol},
            "units": units, "rows": page_rows,
            "totals": totals,
            "diagnostics": diagnostics,
            "page": params["page"], "page_size": params["page_size"],
            "page_count": max(1, (len(top_keys) + params["page_size"] - 1) // params["page_size"]),
            "operation_columns": list(OPERATIONS) if params["columns"] == "operations" else [],
        }

    @api.model
    def get_details(self, options, row_key, column_key, revision):
        if not isinstance(row_key, str) or not isinstance(column_key, str) or column_key not in (
                "opening", "closing", "incoming", "outgoing", "valuation_delta", *OPERATIONS):
            raise UserError(self.env._("Invalid report cell."))
        if not isinstance(revision, str) or len(revision) != 64:
            raise UserError(self.env._("Refresh the report before opening details."))
        params, rows, _diagnostics, _canonical, current = self._calculate(options)
        if current != revision:
            raise UserError(self.env._("The report sources changed. Refresh the report."))
        row = next((entry for entry in rows if entry["key"] == row_key), None)
        if row is None:
            raise AccessError(self.env._("The requested report row is unavailable."))
        events = row["events"]
        if column_key in OPERATIONS:
            events = [event for event in events if event["operation"] == column_key]
        elif column_key in ("incoming", "outgoing"):
            direction = 1 if column_key == "incoming" else -1
            events = [event for event in events if event["quantity"] * direction > 0
                      and event.get("boundary", True)]
        elif column_key in ("opening", "closing"):
            events = self._balance_details(params, row["path"], column_key)
        else:
            events = []
        return {
            "row_key": row_key, "column_key": column_key, "revision": current,
            "measures": row["measures"], "operations": row["operations"],
            "events": events, "diagnostics": row["diagnostics"],
            "explanation": (self.env._(
                "Valuation difference reconciles allocated stock values and recorded movement values; it is not a posted operation.")
                if column_key == "valuation_delta" else ""),
        }

    @api.model
    def get_filter_values(self, options, field_name, search_term="", limit=30):
        params = self._normalize(options or {})
        model_by_field = {
            "product_ids": "product.product", "category_ids": "product.category",
            "warehouse_ids": "stock.warehouse", "location_ids": "stock.location",
            "receipt_ids": "stock.move", "purchase_order_ids": "purchase.order",
        }
        if field_name not in model_by_field or not isinstance(search_term, str) or type(limit) is not int or not 1 <= limit <= 100:
            raise UserError(self.env._("Invalid filter search."))
        model_name = model_by_field[field_name]
        Model = self.env[model_name].with_context(active_test=False)
        if not Model.has_access("read"):
            return []
        if field_name == "receipt_ids":
            Purchase = self.env["purchase.order"]
            order_ids = Purchase.search([
                ("company_id", "=", params["company"].id),
                ("name", "ilike", search_term),
            ]).ids if Purchase.has_access("read") else []
            domain = ["|", "|", ("product_id", "ilike", search_term),
                      ("picking_id.name", "ilike", search_term),
                      ("purchase_line_id.order_id", "in", order_ids)]
        else:
            domain = [("display_name", "ilike", search_term)]
        if field_name == "product_ids":
            domain += [("is_storable", "=", True), "|", ("company_id", "=", False), ("company_id", "=", params["company"].id)]
        elif field_name == "warehouse_ids":
            domain += [("company_id", "=", params["company"].id)]
        elif field_name == "location_ids":
            domain += [("id", "in", list(params["all_locations"]))]
        elif field_name == "receipt_ids":
            domain += [("company_id", "=", params["company"].id), ("state", "=", "done"), ("is_in", "=", True)]
        elif field_name == "purchase_order_ids":
            domain += [("company_id", "=", params["company"].id)]
        records = Model.search(domain, limit=limit)
        if field_name == "receipt_ids":
            result = []
            for move in records:
                purchase_line = move.purchase_line_id
                order = (purchase_line.order_id if purchase_line and purchase_line.has_access("read")
                         else self.env["purchase.order"])
                visible_order = order if order and order.has_access("read") else None
                result.append({"id": move.id, "name": self._receipt_label(move, visible_order)})
            return result
        return [{"id": record.id, "name": record.display_name} for record in records]
    @api.model
    def _detail_path_matches(self, params, path, product, location=None, receipt_id=None):
        values = {
            "product": product.id, "category": product.categ_id.id,
            "receipt": receipt_id,
        }
        if location:
            values.update({
                "location": location.id,
                "warehouse": location.warehouse_id.id or 0,
            })
        return all(values.get(dimension) == record_id for dimension, record_id in path)

    @api.model
    def _balance_details(self, params, path, section):
        product_ids = params["products"].ids
        if not product_ids:
            return []
        if params["mode"] == "receipts":
            collected = self._collect(params)
            leaves, _diagnostics = self._receipt_leaves(params, collected)
            events = []
            for leaf in leaves.values():
                if params["ids"]["receipt_ids"] and leaf["receipt_id"] not in params["ids"]["receipt_ids"]:
                    continue
                if params["ids"]["purchase_order_ids"] and leaf["purchase_order_id"] not in params["ids"]["purchase_order_ids"]:
                    continue
                product = params["products"].browse(leaf["product_id"])
                if not self._detail_path_matches(params, path, product,
                                                 receipt_id=leaf["receipt_id"]):
                    continue
                receipt_id = leaf["receipt_id"]
                events.append({
                    "source": "standard_fifo_stack" if receipt_id > 0 else "unattributed",
                    "date": fields.Datetime.to_string(
                        self.env["stock.move"].browse(receipt_id).date) if receipt_id > 0 else "",
                    "quantity": leaf[section + "_qty"], "amount": leaf[section + "_value"],
                    "operation": "receipt_basis",
                    "document_model": "stock.move" if receipt_id > 0 else "",
                    "document_id": receipt_id if receipt_id > 0 else 0,
                })
            return events
        collected = self._collect(params)
        amounts, _diagnostics = self._endpoint(params, collected, section)
        boundary = params["start" if section == "opening" else "end"]
        parts = defaultdict(list)
        quants = self.env["stock.quant"].with_context(active_test=False).search([
            ("company_id", "=", params["company"].id),
            ("product_id", "in", product_ids),
            ("location_id", "in", list(params["scope_locations"])),
            ("owner_id", "in", [False, params["company"].partner_id.id]),
        ])
        for quant in quants:
            key = (quant.product_id.id, quant.lot_id.id or 0, quant.location_id.id)
            parts[key].append({
                "source": "current_quant", "date": "",
                "quantity": quant.quantity, "operation": "balance_source",
                "document_model": "stock.quant", "document_id": quant.id,
            })
        for line in collected["lines"]:
            if line.move_id.date < boundary:
                continue
            for location, sign in ((line.location_id, 1), (line.location_dest_id, -1)):
                if location.id not in params["scope_locations"]:
                    continue
                key = (line.product_id.id, line.lot_id.id or 0, location.id)
                parts[key].append({
                    "source": "reversed_completed_move",
                    "date": fields.Datetime.to_string(line.move_id.date),
                    "quantity": sign * line.quantity_product_uom,
                    "operation": "balance_source",
                    "document_model": "stock.move", "document_id": line.move_id.id,
                })
        events = []
        currency = params["company"].currency_id
        for key, quantity in collected["balances"][section].items():
            product_id, lot_id, location_id = key
            if location_id not in params["scope_locations"] or not quantity:
                continue
            product = params["products"].browse(product_id)
            location = self.env["stock.location"].browse(location_id)
            if not self._detail_path_matches(params, path, product, location):
                continue
            contributing = list(parts[key])
            remainder_qty = quantity - sum(part["quantity"] for part in contributing)
            if not product.uom_id.is_zero(remainder_qty):
                contributing.append({
                    "source": "reconstruction_remainder", "date": "",
                    "quantity": remainder_qty, "operation": "balance_source",
                    "document_model": "", "document_id": 0,
                })
            value = amounts.get(key)
            remaining_value = currency.round(value) if value is not None else None
            for index, part in enumerate(contributing):
                amount = None
                if remaining_value is not None:
                    amount = (currency.round(value * part["quantity"] / quantity)
                              if index < len(contributing) - 1 else currency.round(remaining_value))
                    remaining_value -= amount
                events.append({
                    **part, "amount": amount,
                    "allocation_basis": ("valuation_lot_allocation" if product.lot_valuated
                                         else "company_valuation_allocation"),
                    "uom_id": product.uom_id.id, "product_id": product_id,
                    "location_id": location_id, "lot_id": lot_id,
                })
        return events
