"""Read-only product stock turnover statement.

The service returns JSON-compatible dictionaries. Monetary values are in the
selected company's currency and quantities are in each product's base unit.
An unavailable monetary value is represented by ``None`` and accompanied by
a diagnostic; zero remains a recorded/calculated zero.
"""

from bisect import bisect_left
from collections import defaultdict
import hashlib
from io import BytesIO
import json
from datetime import date, datetime, time, timedelta, timezone

import pytz

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class ProductStockTurnoverReport(models.AbstractModel):
    _name = "stock.product.turnover.report"
    _description = "Product Stock Turnover Report"

    @api.model
    def _normalize_options(self, options):
        """Validate every client filter and return the single-company scope."""
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise AccessError(self.env._("Inventory manager access is required."))
        if not isinstance(options, dict):
            raise UserError(self.env._("Invalid report filters."))

        company_id = options.get("company_id") or self.env.company.id
        if not isinstance(company_id, int) or isinstance(company_id, bool):
            raise UserError(self.env._("Invalid company filter."))
        if company_id not in self.env.user.company_ids.ids:
            raise AccessError(self.env._("The selected company is unavailable."))
        company = self.env["res.company"].browse(company_id)
        company.check_access("read")
        context = dict(self.env.context)
        for key in (
            "location", "warehouse", "warehouse_id", "owners", "owner_id",
            "lot_id", "package_id", "to_date", "from_date", "at_date",
            "fifo_qty_already_processed", "pos_historical_fifo_date",
        ):
            context.pop(key, None)
        context.update(allowed_company_ids=[company.id], active_test=False)
        scoped = self.with_company(company).with_context(context)
        return scoped._normalize_company_options(options, company)

    @api.model
    def _normalize_company_options(self, options, company):
        tz_name = self.env.user.tz or "UTC"
        try:
            user_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            raise UserError(self.env._("Invalid user time zone."))
        today = datetime.now(user_tz).date()

        def parse_day(value, default):
            if value in (None, False, ""):
                return default
            if isinstance(value, datetime):
                raise UserError(self.env._("A calendar date is required."))
            try:
                return value if isinstance(value, date) else date.fromisoformat(value)
            except (TypeError, ValueError):
                raise UserError(self.env._("Invalid report date."))

        date_from = parse_day(options.get("date_from"), today.replace(day=1))
        date_to = parse_day(options.get("date_to"), today)
        if date_from > date_to or date_to > today:
            raise UserError(self.env._("The report date range is invalid or ends in the future."))

        def to_utc(value):
            return value.astimezone(timezone.utc).replace(tzinfo=None)

        try:
            start = to_utc(user_tz.localize(datetime.combine(date_from, time.min), is_dst=None))
            end = to_utc(user_tz.localize(datetime.combine(date_to + timedelta(days=1), time.min), is_dst=None))
        except (pytz.AmbiguousTimeError, pytz.NonExistentTimeError):
            raise UserError(self.env._("The selected date has an ambiguous local boundary."))
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        supplied_cutoff = options.get("cutoff")
        if supplied_cutoff:
            try:
                cutoff = datetime.fromisoformat(supplied_cutoff)
            except (TypeError, ValueError):
                raise UserError(self.env._("Invalid calculation cutoff."))
            if cutoff.tzinfo or cutoff > now or cutoff < start:
                raise UserError(self.env._("Invalid calculation cutoff."))
        else:
            cutoff = now
        effective_end = min(end, cutoff + timedelta(microseconds=1))

        def ids(name):
            value = options.get(name) or []
            if not isinstance(value, list) or any(
                not isinstance(item, int) or isinstance(item, bool) or item <= 0
                for item in value
            ):
                raise UserError(self.env._("Invalid report selection."))
            return sorted(set(value))

        def one_id(name):
            value = options.get(name)
            if value in (None, False, ""):
                return False
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise UserError(self.env._("Invalid report selection."))
            return value

        if "show_lots" in options:
            raise UserError(self.env._("Refresh the report filters to use FIFO receipts."))
        show_fifo_receipts = options.get("show_fifo_receipts", False)
        if not isinstance(show_fifo_receipts, bool):
            raise UserError(self.env._("Invalid FIFO receipt option."))
        warehouse_id = one_id("warehouse_id")
        location_id = one_id("location_id")
        include_children = options.get("include_children", True)
        if not isinstance(include_children, bool):
            raise UserError(self.env._("Invalid child-location filter."))

        Warehouse = self.env["stock.warehouse"].with_context(active_test=False)
        Location = self.env["stock.location"].with_context(active_test=False)
        Product = self.env["product.product"].with_context(active_test=False)
        Category = self.env["product.category"].with_context(active_test=False)
        for model in (Warehouse, Location, Product, Category):
            model.check_access("read")

        warehouse = Warehouse.browse(warehouse_id) if warehouse_id else Warehouse
        location = Location.browse(location_id) if location_id else Location
        if warehouse and (not warehouse.exists() or warehouse.company_id != company):
            raise UserError(self.env._("The warehouse does not belong to the selected company."))
        if location and (not location.exists() or location.company_id != company):
            raise UserError(self.env._("The location does not belong to the selected company."))
        if warehouse:
            warehouse.check_access("read")
        if location:
            location.check_access("read")
        if warehouse and location and location not in Location.search([
            ("id", "child_of", warehouse.view_location_id.id),
        ]):
            raise UserError(self.env._("The location is outside the selected warehouse."))

        valued_domain = [
            ("company_id", "=", company.id),
            ("usage", "in", ["internal", "transit"]),
        ]
        valued_locations = Location.search(valued_domain)
        all_location_ids = set(valued_locations.ids)
        if warehouse:
            scope_domain = [("id", "child_of", warehouse.view_location_id.id)]
        elif location:
            scope_domain = [("id", "child_of", location.id)] if include_children else [("id", "=", location.id)]
        else:
            scope_domain = []
        if warehouse and location:
            scope_domain += [("id", "child_of", location.id)] if include_children else [("id", "=", location.id)]
        scope_ids = set(Location.search(valued_domain + scope_domain).ids)

        product_ids = ids("product_ids")
        category_ids = ids("category_ids")
        products = Product.browse(product_ids)
        categories = Category.browse(category_ids)
        if len(products.exists()) != len(product_ids) or len(categories.exists()) != len(category_ids):
            raise UserError(self.env._("A selected product or category is unavailable."))
        products.check_access("read")
        categories.check_access("read")
        if any(product.company_id and product.company_id != company for product in products):
            raise UserError(self.env._("A selected product belongs to another company."))

        product_domain = [("is_storable", "=", True),
                          "|", ("company_id", "=", False), ("company_id", "=", company.id)]
        if product_ids:
            product_domain.append(("id", "in", product_ids))
        if category_ids:
            product_domain.append(("categ_id", "in", category_ids))
        selected_products = Product.search(product_domain)
        self._check_complete_visibility(
            company, all_location_ids, selected_products, product_domain,
        )

        return {
            "_service": self,
            "company": company,
            "date_from": date_from,
            "date_to": date_to,
            "timezone": tz_name,
            "start": start,
            "end": effective_end,
            "cutoff": cutoff,
            "warehouse": warehouse,
            "location": location,
            "include_children": include_children,
            "show_fifo_receipts": show_fifo_receipts,
            "all_location_ids": all_location_ids,
            "scope_ids": scope_ids,
            "products": selected_products,
            "product_ids": product_ids,
            "category_ids": category_ids,
        }

    @api.model
    def _check_complete_visibility(self, company, all_location_ids, products, product_domain):
        """Refuse a result when normal rules hide any valuation input.

        Sudo is limited to existence counts. Hidden records and their values
        never enter the returned report or a user-visible error.
        """
        denied = self.env._("The report sources are not fully accessible.")
        Product = self.env["product.product"].with_context(active_test=False)
        if Product.search_count(product_domain) != Product.sudo().search_count(product_domain):
            raise AccessError(denied)
        if not products:
            return

        location_domain = [
            ("company_id", "=", company.id),
            ("usage", "in", ["internal", "transit"]),
        ]
        source_domains = {
            "stock.location": location_domain,
            "stock.quant": [
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
                ("location_id", "in", list(all_location_ids)),
                ("owner_id", "in", [False, company.partner_id.id]),
            ],
            "stock.move": [
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
                ("state", "=", "done"),
            ],
            "stock.move.line": [
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
                ("move_id.state", "=", "done"),
                ("owner_id", "in", [False, company.partner_id.id]),
            ],
            "stock.lot": [
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
            ],
            "product.value": [
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
            ],
        }
        for name, domain in source_domains.items():
            model = self.env[name].with_context(active_test=False)
            model.check_access("read")
            if model.search_count(domain) != model.sudo().search_count(domain):
                raise AccessError(denied)

    @api.model
    def _collect_quantities(self, params):
        """Reconstruct both boundaries from current quants and completed lines."""
        company = params["company"]
        product_ids = params["products"].ids
        own_owners = [False, company.partner_id.id]
        all_ids = params["all_location_ids"]
        scope_ids = params["scope_ids"]
        result = {
            "current_scope": defaultdict(float),
            "current_company": defaultdict(float),
            "opening_scope": defaultdict(float),
            "opening_company": defaultdict(float),
            "closing_scope": defaultdict(float),
            "closing_company": defaultdict(float),
            "historical_scope": defaultdict(float),
            "lines": [],
            "period_lines": [],
        }
        if not product_ids:
            return result

        Quant = self.env["stock.quant"].with_context(active_test=False)
        for product, lot, location, quantity in Quant._read_group(
            [
                ("company_id", "=", company.id),
                ("product_id", "in", product_ids),
                ("location_id", "in", list(all_ids)),
                ("owner_id", "in", own_owners),
            ],
            ["product_id", "lot_id", "location_id"],
            ["quantity:sum"],
        ):
            key = (product.id, lot.id or False)
            result["current_company"][key] += quantity
            if location.id in scope_ids:
                result["current_scope"][key] += quantity

        for name in ("scope", "company"):
            current = result["current_" + name]
            result["opening_" + name].update(current)
            result["closing_" + name].update(current)

        Line = self.env["stock.move.line"].with_context(active_test=False)
        lines = Line.search_fetch(
            [
                ("company_id", "=", company.id),
                ("product_id", "in", product_ids),
                ("move_id.state", "=", "done"),
                ("owner_id", "in", own_owners),
            ],
            [
                "product_id", "lot_id", "location_id", "location_dest_id",
                "quantity_product_uom", "move_id", "date", "picked",
            ],
        )
        moves = lines.mapped("move_id")
        moves.fetch(["date", "value", "is_in", "is_out", "state"])
        for line in lines:
            qty = line.quantity_product_uom
            if not qty:
                continue
            move_date = line.move_id.date
            if not move_date:
                continue
            key = (line.product_id.id, line.lot_id.id or False)
            src = line.location_id.id
            dst = line.location_dest_id.id
            company_delta = qty * (int(dst in all_ids) - int(src in all_ids))
            scope_delta = qty * (int(dst in scope_ids) - int(src in scope_ids))
            result["historical_scope"][key] += scope_delta
            if move_date >= params["start"]:
                result["opening_scope"][key] -= scope_delta
                result["opening_company"][key] -= company_delta
            if move_date >= params["end"]:
                result["closing_scope"][key] -= scope_delta
                result["closing_company"][key] -= company_delta
            result["lines"].append(line)
            if params["start"] <= move_date < params["end"] and scope_delta:
                result["period_lines"].append(line)
        return result

    @api.model
    def _endpoint_values(self, params, quantities, boundary, quantity_name):
        """Allocate standard product or lot value at one exact UTC boundary."""
        company = params["company"]
        products = params["products"]
        values = {}
        diagnostics = defaultdict(list)
        if not products:
            return values, diagnostics

        at_date = boundary - timedelta(microseconds=1)
        context = {
            "to_date": at_date,
            "at_date": at_date,
            "location": list(params["all_location_ids"]),
            "owners": [False, company.partner_id.id],
            "strict": True,
            "allowed_company_ids": [company.id],
            "active_test": False,
        }
        valued_products = products.with_context(context)
        product_values = {product.id: product.total_value for product in valued_products}
        standard_qty = {product.id: product.qty_available for product in valued_products}
        lot_products = products.filtered("lot_valuated")
        lots = self.env["stock.lot"].with_context(context).search([
            ("product_id", "in", lot_products.ids),
            ("company_id", "=", company.id),
        ])
        lot_values = {lot.id: (lot.total_value, lot.product_qty) for lot in lots}

        company_qty = quantities[quantity_name + "_company"]
        scope_qty = quantities[quantity_name + "_scope"]
        by_product_company = defaultdict(float)
        by_product_scope = defaultdict(float)
        for (product_id, _lot_id), qty in company_qty.items():
            by_product_company[product_id] += qty
        for (product_id, _lot_id), qty in scope_qty.items():
            by_product_scope[product_id] += qty

        Value = self.env["product.value"]
        Move = self.env["stock.move"]
        historical = at_date < params["cutoff"] - timedelta(microseconds=1)
        manual_ids = set()
        valued_move_ids = set()
        if historical:
            manual_ids = set(Value.search([
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
                ("date", "<=", at_date),
                ("move_id", "=", False),
            ]).mapped("product_id").ids)
            valued_move_ids = set(Move.search([
                ("company_id", "=", company.id),
                ("product_id", "in", products.ids),
                ("date", "<=", at_date),
                ("state", "=", "done"),
                "|", ("is_in", "=", True), ("is_out", "=", True),
            ]).mapped("product_id").ids)

        for product in products:
            pid = product.id
            total_company_qty = by_product_company[pid]
            if product.uom_id.compare(total_company_qty, standard_qty[pid]):
                diagnostics[pid].append({
                    "code": "standard_quantity_mismatch",
                    "message": self.env._("Recorded quantity differs from the standard valuation quantity."),
                    "boundary": fields.Datetime.to_string(at_date),
                })
            if product.lot_valuated:
                if historical and product.cost_method == "standard" and not product.uom_id.is_zero(by_product_scope[pid]):
                    values[pid] = None
                    diagnostics[pid].append({
                        "code": "missing_historical_lot_basis",
                        "message": self.env._("Standard lot cost has no supported historical snapshot."),
                        "boundary": fields.Datetime.to_string(at_date),
                    })
                    continue
                lot_keys = {
                    key for key in set(company_qty) | set(scope_qty)
                    if key[0] == pid
                }
                total = 0.0
                incomplete = False
                for key in lot_keys:
                    _pid, lot_id = key
                    selected_qty = scope_qty.get(key, 0.0)
                    company_lot_qty = company_qty.get(key, 0.0)
                    if product.uom_id.is_zero(selected_qty):
                        continue
                    if not lot_id or lot_id not in lot_values:
                        incomplete = True
                        diagnostics[pid].append({
                            "code": "missing_lot_basis",
                            "message": self.env._("A valuation lot is unavailable."),
                            "boundary": fields.Datetime.to_string(at_date),
                        })
                        continue
                    standard_lot_value, standard_lot_qty = lot_values[lot_id]
                    if product.uom_id.is_zero(company_lot_qty) or product.uom_id.is_zero(standard_lot_qty):
                        incomplete = True
                        diagnostics[pid].append({
                            "code": "zero_valuation_denominator",
                            "message": self.env._("The lot valuation quantity is zero while selected stock is not."),
                            "boundary": fields.Datetime.to_string(at_date),
                        })
                        continue
                    total += selected_qty * standard_lot_value / standard_lot_qty
                values[pid] = None if incomplete else total
            else:
                selected_qty = by_product_scope[pid]
                if product.uom_id.is_zero(selected_qty):
                    values[pid] = 0.0
                elif product.uom_id.is_zero(total_company_qty) or product.uom_id.is_zero(standard_qty[pid]):
                    values[pid] = None
                    diagnostics[pid].append({
                        "code": "zero_valuation_denominator",
                        "message": self.env._("Company valuation quantity is zero while selected stock is not."),
                        "boundary": fields.Datetime.to_string(at_date),
                    })
                elif historical and pid not in manual_ids and (
                    product.cost_method == "standard" or pid not in valued_move_ids
                ):
                    values[pid] = None
                    diagnostics[pid].append({
                        "code": "missing_historical_basis",
                        "message": self.env._("Historical valuation has no recorded cost basis."),
                        "boundary": fields.Datetime.to_string(at_date),
                    })
                else:
                    values[pid] = selected_qty * product_values[pid] / standard_qty[pid]
        return values, diagnostics

    @api.model
    def _movement_values(self, params, quantities):
        """Allocate recorded external costs and historical internal costs."""
        company = params["company"]
        all_ids = params["all_location_ids"]
        scope_ids = params["scope_ids"]
        currency = company.currency_id
        move_lines = defaultdict(list)
        for line in quantities["lines"]:
            move_lines[line.move_id.id].append(line)

        amounts = {}
        diagnostics = defaultdict(list)
        for move_id, lines in move_lines.items():
            move = lines[0].move_id
            external = [
                line for line in lines
                if (line.location_id.id in all_ids) != (line.location_dest_id.id in all_ids)
            ]
            if external:
                denominator = sum(line.quantity_product_uom for line in external)
                if not denominator:
                    for line in external:
                        amounts[line.id] = None
                    diagnostics[move.product_id.id].append({
                        "code": "missing_movement_denominator",
                        "message": self.env._("The movement has no valued own-stock quantity."),
                    })
                else:
                    remainder = currency.round(move.value)
                    for line in sorted(external, key=lambda item: item.id)[:-1]:
                        share = currency.round(move.value * line.quantity_product_uom / denominator)
                        amounts[line.id] = share
                        remainder -= share
                    amounts[sorted(external, key=lambda item: item.id)[-1].id] = currency.round(remainder)

        # Internal transfers do not change company stock or its valuation.
        # Reuse the standard pre-transfer valuation until an event can change
        # the company (or lot) basis. A matching timestamp is excluded by
        # bisect_left, in line with the pre-timestamp valuation context.
        valuation_events = defaultdict(set)
        for line in quantities["lines"]:
            if (line.location_id.id in all_ids) != (line.location_dest_id.id in all_ids):
                valuation_events[line.product_id.id].add(line.move_id.date)
        Value = self.env["product.value"]
        for value in Value.search_fetch([
            ("company_id", "=", company.id),
            ("product_id", "in", params["products"].ids),
            ("date", "<=", params["cutoff"]),
        ], ["product_id", "date"]):
            valuation_events[value.product_id.id].add(value.date)
        valuation_events = {
            product_id: sorted(dates)
            for product_id, dates in valuation_events.items()
        }
        internal_cache = {}
        for line in quantities["period_lines"]:
            if line.id in amounts:
                continue
            if line.location_id.id not in all_ids or line.location_dest_id.id not in all_ids:
                amounts[line.id] = None
                diagnostics[line.product_id.id].append({
                    "code": "unvalued_crossing",
                    "message": self.env._("The crossing has no supported valuation basis."),
                })
                continue
            product_id = line.product_id.id
            epoch = bisect_left(valuation_events.get(product_id, ()), line.move_id.date)
            key = (product_id, line.lot_id.id or False, epoch)
            if key not in internal_cache:
                internal_cache[key] = self._internal_unit_cost(params, quantities, line)
            unit_cost = internal_cache[key]
            if unit_cost is None:
                amounts[line.id] = None
                diagnostics[line.product_id.id].append({
                    "code": "missing_internal_basis",
                    "message": self.env._("Historical internal transfer cost is unavailable."),
                })
            else:
                amounts[line.id] = currency.round(line.quantity_product_uom * unit_cost)
        return amounts, diagnostics

    @api.model
    def _internal_unit_cost(self, params, quantities, line):
        """Use one pre-timestamp company/lot basis for both transfer sides."""
        product = line.product_id
        company = params["company"]
        transfer_time = line.move_id.date
        lot_id = line.lot_id.id or False
        key = (product.id, lot_id)
        current = quantities["current_company"]
        company_qty = (
            current.get(key, 0.0) if product.lot_valuated else
            sum(qty for (pid, _lot_id), qty in current.items() if pid == product.id)
        )
        for history_line in quantities["lines"]:
            if history_line.product_id.id != product.id or history_line.move_id.date < transfer_time:
                continue
            if product.lot_valuated and (history_line.lot_id.id or False) != lot_id:
                continue
            delta = history_line.quantity_product_uom * (
                int(history_line.location_dest_id.id in params["all_location_ids"])
                - int(history_line.location_id.id in params["all_location_ids"])
            )
            company_qty -= delta
        if product.uom_id.is_zero(company_qty):
            return None
        at_date = transfer_time - timedelta(microseconds=1)
        context = {
            "to_date": at_date,
            "at_date": at_date,
            "location": list(params["all_location_ids"]),
            "owners": [False, company.partner_id.id],
            "strict": True,
            "allowed_company_ids": [company.id],
            "active_test": False,
        }
        Value = self.env["product.value"]
        manual_domain = [
            ("company_id", "=", company.id),
            ("product_id", "=", product.id),
            ("date", "<=", at_date),
            ("move_id", "=", False),
        ]
        if product.lot_valuated:
            manual_domain.append(("lot_id", "in", [False, lot_id]))
        if product.lot_valuated and product.cost_method == "standard":
            return None
        if product.cost_method == "standard" and not Value.search_count(manual_domain):
            return None
        if product.lot_valuated:
            if not lot_id:
                return None
            lot = self.env["stock.lot"].browse(lot_id).with_context(context)
            if not lot.exists():
                return None
            standard_qty = lot.product_qty
            standard_value = lot.total_value
        else:
            valued_product = product.with_context(context)
            standard_qty = valued_product.qty_available
            standard_value = valued_product.total_value
        if product.uom_id.is_zero(standard_qty):
            return None
        if product.uom_id.compare(company_qty, standard_qty):
            return None
        return standard_value / standard_qty

    @api.model
    def get_report(self, options=None):
        """Return complete rows, totals, filters, source diagnostics and metadata."""
        params = self._normalize_options({} if options is None else options)
        service = params["_service"]
        quantities = service._collect_quantities(params)
        opening_values, opening_diag = service._endpoint_values(
            params, quantities, params["start"], "opening",
        )
        closing_values, closing_diag = service._endpoint_values(
            params, quantities, params["end"], "closing",
        )
        movement_values, movement_diag = service._movement_values(params, quantities)
        currency = params["company"].currency_id
        rows = []
        monetary_fields = (
            "opening_value", "incoming_value", "outgoing_value",
            "valuation_difference", "closing_value",
        )
        totals = {field: 0.0 for field in monetary_fields}
        totals["incomplete"] = False
        unit_totals = defaultdict(lambda: {
            "opening_qty": 0.0, "incoming_qty": 0.0,
            "outgoing_qty": 0.0, "closing_qty": 0.0,
        })
        by_product = defaultdict(list)
        for line in quantities["period_lines"]:
            by_product[line.product_id.id].append(line)
        for product in params["products"]:
            pid = product.id
            unit = product.uom_id
            keys = {key for key in set(quantities["opening_scope"]) | set(quantities["closing_scope"]) if key[0] == pid}
            opening_qty = sum(quantities["opening_scope"].get(key, 0.0) for key in keys)
            closing_qty = sum(quantities["closing_scope"].get(key, 0.0) for key in keys)
            current_qty = sum(value for (p_id, _lot_id), value in quantities["current_scope"].items() if p_id == pid)
            history_qty = sum(value for (p_id, _lot_id), value in quantities["historical_scope"].items() if p_id == pid)
            incoming_qty = 0.0
            outgoing_qty = 0.0
            incoming_amounts = []
            outgoing_amounts = []
            for line in by_product[pid]:
                qty = line.quantity_product_uom
                if line.location_dest_id.id in params["scope_ids"]:
                    incoming_qty += qty
                    incoming_amounts.append(movement_values.get(line.id))
                else:
                    outgoing_qty += qty
                    outgoing_amounts.append(movement_values.get(line.id))
            diagnostics = opening_diag[pid] + closing_diag[pid] + movement_diag[pid]
            if not unit.is_zero(opening_qty + incoming_qty - outgoing_qty - closing_qty):
                diagnostics.append({
                    "code": "quantity_reconciliation",
                    "message": self.env._("Opening quantity and period movements do not reconcile with closing quantity."),
                    "delta": unit.round(opening_qty + incoming_qty - outgoing_qty - closing_qty),
                })
            if not unit.is_zero(current_qty - history_qty):
                diagnostics.append({
                    "code": "unexplained_current_quantity",
                    "message": self.env._("Current stock differs from the recorded completed movement history."),
                    "delta": unit.round(current_qty - history_qty),
                })
            opening_value = opening_values.get(pid, 0.0)
            closing_value = closing_values.get(pid, 0.0)
            incoming_value = None if None in incoming_amounts else currency.round(sum(incoming_amounts))
            outgoing_value = None if None in outgoing_amounts else currency.round(sum(outgoing_amounts))
            opening_value = None if opening_value is None else currency.round(opening_value)
            closing_value = None if closing_value is None else currency.round(closing_value)
            operands = (opening_value, incoming_value, outgoing_value, closing_value)
            difference = None if None in operands else currency.round(
                closing_value - opening_value - incoming_value + outgoing_value
            )
            row = {
                "product_id": pid,
                "default_code": product.default_code or "",
                "name": product.display_name,
                "uom_id": unit.id,
                "uom_name": unit.name,
                "opening_qty": unit.round(opening_qty),
                "opening_value": opening_value,
                "incoming_qty": unit.round(incoming_qty),
                "incoming_value": incoming_value,
                "outgoing_qty": unit.round(outgoing_qty),
                "outgoing_value": outgoing_value,
                "valuation_difference": difference,
                "closing_qty": unit.round(closing_qty),
                "closing_value": closing_value,
                "closing_unit_cost": closing_value / closing_qty if closing_value is not None and not unit.is_zero(closing_qty) else None,
                "diagnostics": diagnostics,
                "valuation_method": "proportional_standard_allocation",
            }
            if not any((
                not unit.is_zero(opening_qty), not unit.is_zero(closing_qty),
                not unit.is_zero(incoming_qty), not unit.is_zero(outgoing_qty),
                opening_value not in (None, 0.0), closing_value not in (None, 0.0),
                diagnostics,
            )):
                continue
            rows.append(row)
            subtotals = unit_totals[unit.id]
            for name in subtotals:
                subtotals[name] += row[name]
            for field in monetary_fields:
                if row[field] is None:
                    totals["incomplete"] = True
                else:
                    totals[field] += row[field]
        if params["show_fifo_receipts"]:
            for row in rows:
                product = params["products"].browse(row["product_id"])
                row["fifo_receipts"] = {
                    boundary: service._fifo_receipt_basis(params, quantities, product, boundary)
                    for boundary in ("opening", "closing")
                }
        for field in monetary_fields:
            totals[field] = currency.round(totals[field])
        result = {
            "options": {
                "company_id": params["company"].id,
                "date_from": params["date_from"].isoformat(),
                "date_to": params["date_to"].isoformat(),
                "warehouse_id": params["warehouse"].id or False,
                "location_id": params["location"].id or False,
                "include_children": params["include_children"],
                "show_fifo_receipts": params["show_fifo_receipts"],
                "product_ids": params["product_ids"],
                "category_ids": params["category_ids"],
                "cutoff": params["cutoff"].isoformat(timespec="microseconds"),
            },
            "timezone": params["timezone"],
            "currency_id": currency.id,
            "currency_name": currency.name,
            "generated_at": fields.Datetime.to_string(fields.Datetime.now()),
            "effective_start": fields.Datetime.to_string(params["start"]),
            "effective_end": fields.Datetime.to_string(params["end"]),
            "rows": rows,
            "totals": totals,
            "unit_totals": [
                {"uom_id": unit_id, "uom_name": self.env["uom.uom"].browse(unit_id).name, **values}
                for unit_id, values in unit_totals.items()
            ],
        }
        result["fingerprint"] = service._fingerprint(params, quantities, result)
        return result

    @api.model
    def _fifo_receipt_basis(self, params, quantities, product, boundary):
        """Read standard FIFO receipt layers for a company valuation boundary."""
        result = {
            "applicable": product.cost_method == "fifo",
            "scope": "company",
            "location_selected": params["scope_ids"] != params["all_location_ids"],
            "boundary": boundary,
            "receipts": [],
            "unattributed_quantity": 0.0,
            "unattributed_value": 0.0,
            "diagnostics": [],
        }
        if not result["applicable"]:
            return result
        company = params["company"]
        at_date = params["start" if boundary == "opening" else "end"] - timedelta(microseconds=1)
        context = {
            "to_date": at_date,
            "at_date": at_date,
            "location": list(params["all_location_ids"]),
            "owners": [False, company.partner_id.id],
            "strict": True,
            "allowed_company_ids": [company.id],
            "active_test": False,
        }
        valued_product = product.with_context(context)
        company_qty = valued_product.qty_available
        company_value = valued_product.total_value
        result["company_quantity"] = product.uom_id.round(company_qty)
        result["company_value"] = company.currency_id.round(company_value)
        bases = [(False, company_qty)]
        if product.lot_valuated:
            lot_quantities = quantities[boundary + "_company"]
            lot_ids = sorted(lot_id for (pid, lot_id), qty in lot_quantities.items()
                             if pid == product.id and lot_id and qty > 0)
            lots = self.env["stock.lot"].browse(lot_ids).with_context(context)
            lots.check_access("read")
            bases = [(lot, lot.product_qty) for lot in lots]
        receipts = []
        raw_values = []
        for lot, qty in bases:
            if product.uom_id.compare(qty, 0) <= 0:
                continue
            stack, first_quantity = valued_product._run_fifo_get_stack(
                lot=lot or None, at_date=at_date,
            )
            for index, move in enumerate(stack):
                quantity = first_quantity if index == 0 else move._get_valued_qty(lot=lot or None)
                valued_qty = move._get_valued_qty()
                if product.uom_id.compare(quantity, 0) <= 0 or product.uom_id.is_zero(valued_qty):
                    continue
                document = move.picking_id or move
                if not document.has_access("read"):
                    document = move
                unit_cost = move.value / valued_qty
                raw_value = quantity * unit_cost
                raw_values.append(raw_value)
                receipts.append({
                    "move_id": move.id,
                    "lot_id": lot.id if lot else False,
                    "lot_name": lot.name if lot else "",
                    "date": fields.Datetime.to_string(move.date),
                    "document_model": document._name,
                    "document_id": document.id,
                    "document_name": document.display_name,
                    "quantity": product.uom_id.round(quantity),
                    "unit_cost": unit_cost,
                    "value": company.currency_id.round(raw_value),
                })
        result["receipts"] = receipts
        known_qty = sum(item["quantity"] for item in receipts)
        quantity_gap = product.uom_id.round(company_qty - known_qty)
        currency = company.currency_id
        # Per-line currency rounding can accumulate over many receipts. Distribute
        # only that rounding difference; never turn an unexplained value into a receipt.
        rounded_raw_total = currency.round(sum(raw_values))
        if product.uom_id.is_zero(quantity_gap) and currency.is_zero(company_value - rounded_raw_total):
            rounding_gap = currency.round(rounded_raw_total - sum(item["value"] for item in receipts))
            if not currency.is_zero(rounding_gap):
                step = currency.rounding if rounding_gap > 0 else -currency.rounding
                ranked = sorted(
                    range(len(receipts)),
                    key=lambda index: (raw_values[index] - receipts[index]["value"]) * step,
                    reverse=True,
                )
                for index in ranked[:round(abs(rounding_gap / step))]:
                    receipts[index]["value"] = currency.round(receipts[index]["value"] + step)
        known_value = sum(item["value"] for item in receipts)
        value_gap = currency.round(company_value - known_value)
        result["unattributed_quantity"] = quantity_gap
        result["unattributed_value"] = value_gap
        if not product.uom_id.is_zero(quantity_gap) or not company.currency_id.is_zero(value_gap):
            result["diagnostics"].append(self.env._(
                "Part of the FIFO valuation cannot be attributed to recorded receipts."
            ))
        return result

    @api.model
    def _fingerprint(self, params, quantities, result):
        """Bind later requests to visible values and their authorized sources."""
        digest = hashlib.sha256()
        digest.update(json.dumps({
            "options": result["options"],
            "rows": result["rows"],
            "totals": result["totals"],
            "unit_totals": result["unit_totals"],
        }, sort_keys=True, default=str).encode())
        if not params["products"]:
            return digest.hexdigest()
        company = params["company"]
        pid = params["products"].ids
        sources = (
            ("product.product", [("id", "in", pid)], ["id", "write_date", "active", "standard_price", "cost_method", "lot_valuated"]),
            ("stock.location", [("id", "in", list(params["all_location_ids"]))], ["id", "write_date", "location_id", "usage", "active"]),
            ("stock.quant", [
                ("company_id", "=", company.id),
                ("product_id", "in", pid),
                ("location_id", "in", list(params["all_location_ids"])),
                ("owner_id", "in", [False, company.partner_id.id]),
            ], ["id", "write_date", "product_id", "lot_id", "location_id", "owner_id", "quantity"]),
            ("stock.move", [
                ("company_id", "=", company.id), ("product_id", "in", pid), ("state", "=", "done"),
            ], ["id", "write_date", "product_id", "date", "state", "value", "is_in", "is_out"]),
            ("stock.move.line", [
                ("company_id", "=", company.id), ("product_id", "in", pid),
                ("move_id.state", "=", "done"),
                ("owner_id", "in", [False, company.partner_id.id]),
            ], ["id", "write_date", "move_id", "product_id", "lot_id", "location_id",
                "location_dest_id", "owner_id", "quantity_product_uom"]),
            ("stock.lot", [
                ("company_id", "=", company.id), ("product_id", "in", pid),
            ], ["id", "write_date", "product_id", "standard_price"]),
            ("product.value", [
                ("company_id", "=", company.id), ("product_id", "in", pid),
            ], ["id", "write_date", "product_id", "lot_id", "move_id", "date", "value"]),
        )
        for model_name, domain, field_names in sources:
            records = self.env[model_name].with_context(active_test=False).search(domain, order="id")
            digest.update(model_name.encode())
            for offset in range(0, len(records), 500):
                chunk = records[offset:offset + 500].read(field_names, load=None)
                digest.update(json.dumps(chunk, sort_keys=True, default=str).encode())
        return digest.hexdigest()

    @api.model
    def get_details(self, options, product_id, section, expected_fingerprint):
        """Return authorized evidence for one displayed cell."""
        valid_sections = {"opening", "incoming", "outgoing", "difference", "closing"}
        if section not in valid_sections:
            raise UserError(self.env._("Invalid report detail section."))
        if not isinstance(product_id, int) or isinstance(product_id, bool):
            raise UserError(self.env._("Invalid product selection."))
        if not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64:
            raise UserError(self.env._("Refresh the report before opening details."))
        report = self.get_report(options)
        if report["fingerprint"] != expected_fingerprint:
            raise UserError(self.env._("The report sources changed. Refresh the report."))
        row = next((item for item in report["rows"] if item["product_id"] == product_id), None)
        if row is None:
            raise AccessError(self.env._("The requested product is unavailable."))
        params = self._normalize_options(options)
        service = params["_service"]
        quantities = service._collect_quantities(params)
        result = {
            "section": section,
            "product_id": product_id,
            "fingerprint": expected_fingerprint,
            "options": report["options"],
            "row": row,
            "lines": [],
            "explanation": {},
        }
        if section in ("incoming", "outgoing"):
            amounts, _diagnostics = service._movement_values(params, quantities)
            for line in quantities["period_lines"]:
                if line.product_id.id != product_id:
                    continue
                direction = "incoming" if line.location_dest_id.id in params["scope_ids"] else "outgoing"
                if direction != section:
                    continue
                move = line.move_id
                document = move.picking_id if move.picking_id else move
                if not document.has_access("read"):
                    document = move
                result["lines"].append({
                    "move_line_id": line.id,
                    "move_id": move.id,
                    "date": fields.Datetime.to_string(move.date),
                    "line_date": fields.Datetime.to_string(line.date),
                    "quantity": line.quantity_product_uom,
                    "amount": amounts.get(line.id),
                    "source": "recorded_move" if move.is_in or move.is_out else "standard_pre_transfer",
                    "source_location": line.location_id.complete_name,
                    "destination_location": line.location_dest_id.complete_name,
                    "lot_id": line.lot_id.id or False,
                    "lot_name": line.lot_id.name or self.env._("Without lot"),
                    "document_model": document._name,
                    "document_id": document.id,
                    "document_name": document.display_name,
                })
            result["explanation"] = {
                "quantity": row[section + "_qty"],
                "value": row[section + "_value"],
                "rule": self.env._(
                    "Recorded valued movement cost is allocated over owned valued movement quantity; "
                    "internal transfers use standard cost immediately before their timestamp."
                ),
            }
        elif section == "difference":
            values = self.env["product.value"].search([
                ("company_id", "=", params["company"].id),
                ("product_id", "=", product_id),
                ("date", ">=", params["start"]),
                ("date", "<", params["end"]),
            ], order="date,id")
            result["explanation"] = {
                "opening_value": row["opening_value"],
                "incoming_value": row["incoming_value"],
                "outgoing_value": row["outgoing_value"],
                "closing_value": row["closing_value"],
                "difference": row["valuation_difference"],
                "rule": self.env._(
                    "Closing value minus opening value minus incoming value plus outgoing value. "
                    "This reconciles allocated stock value and turnover; it is not necessarily a posted revaluation."
                ),
                "value_events": [
                    {"id": value.id, "date": fields.Datetime.to_string(value.date),
                     "value": value.value, "move_id": value.move_id.id or False}
                    for value in values
                ],
            }
        else:
            boundary = params["start"] if section == "opening" else params["end"]
            current_quants = self.env["stock.quant"].search([
                ("company_id", "=", params["company"].id),
                ("product_id", "=", product_id),
                ("location_id", "in", list(params["scope_ids"])),
                ("owner_id", "in", [False, params["company"].partner_id.id]),
            ])
            result["lines"] = [
                {
                    "source": "current_quant",
                    "quant_id": quant.id,
                    "location": quant.location_id.complete_name,
                    "lot_id": quant.lot_id.id or False,
                    "lot_name": quant.lot_id.name or self.env._("Without lot"),
                    "quantity": quant.quantity,
                }
                for quant in current_quants
            ]
            for line in quantities["lines"]:
                if line.product_id.id != product_id or line.move_id.date < boundary:
                    continue
                direction = int(line.location_dest_id.id in params["scope_ids"]) - int(
                    line.location_id.id in params["scope_ids"]
                )
                if not direction:
                    continue
                move = line.move_id
                document = move.picking_id if move.picking_id else move
                if not document.has_access("read"):
                    document = move
                result["lines"].append({
                    "source": "reversed_completed_crossing",
                    "move_line_id": line.id,
                    "move_id": move.id,
                    "date": fields.Datetime.to_string(move.date),
                    "line_date": fields.Datetime.to_string(line.date),
                    "quantity": -direction * line.quantity_product_uom,
                    "source_location": line.location_id.complete_name,
                    "destination_location": line.location_dest_id.complete_name,
                    "lot_id": line.lot_id.id or False,
                    "lot_name": line.lot_id.name or self.env._("Without lot"),
                    "document_model": document._name,
                    "document_id": document.id,
                    "document_name": document.display_name,
                })
            product = params["products"].browse(product_id)
            at_date = boundary - timedelta(microseconds=1)
            context = {
                "to_date": at_date,
                "at_date": at_date,
                "location": list(params["all_location_ids"]),
                "owners": [False, params["company"].partner_id.id],
                "strict": True,
                "allowed_company_ids": [params["company"].id],
                "active_test": False,
            }
            valued_product = product.with_context(context)
            company_quantity = sum(
                qty for (pid, _lot_id), qty in quantities[section + "_company"].items()
                if pid == product_id
            )
            lot_basis = []
            if product.lot_valuated:
                lot_ids = {
                    basis_lot_id for (pid, basis_lot_id) in
                    (set(quantities[section + "_scope"]) | set(quantities[section + "_company"]))
                    if pid == product_id and basis_lot_id
                }
                for lot in self.env["stock.lot"].browse(sorted(lot_ids)).with_context(context):
                    key = (product_id, lot.id)
                    lot_basis.append({
                        "lot_id": lot.id,
                        "lot_name": lot.name,
                        "company_quantity": quantities[section + "_company"].get(key, 0.0),
                        "selected_quantity": quantities[section + "_scope"].get(key, 0.0),
                        "standard_value": lot.total_value if row[section + "_value"] is not None else None,
                    })
            standard_quantity = valued_product.qty_available
            standard_value = valued_product.total_value if row[section + "_value"] is not None else None
            result["explanation"] = {
                "quantity": row[section + "_qty"],
                "value": row[section + "_value"],
                "company_quantity": company_quantity,
                "standard_quantity": standard_quantity,
                "standard_value": standard_value,
                "lot_basis": lot_basis,
                "valuation_method": row["valuation_method"],
                "boundary": at_date.isoformat(timespec="microseconds"),
                "rule": self.env._(
                    "Endpoint quantity is current owned stock minus completed crossings after the boundary. "
                    "Value is allocated proportionally from the company's standard valuation."
                ),
            }
        return result

    @api.model
    def get_fifo_receipt_document(
        self, options, product_id, boundary, move_id, lot_id, expected_fingerprint,
    ):
        """Reauthorize a receipt link against the fixed statement snapshot."""
        if (
            not isinstance(product_id, int) or isinstance(product_id, bool)
            or not isinstance(move_id, int) or isinstance(move_id, bool)
            or not isinstance(lot_id, int) or isinstance(lot_id, bool)
            or product_id <= 0 or move_id <= 0 or lot_id < 0
            or boundary not in ("opening", "closing")
        ):
            raise UserError(self.env._("Invalid FIFO receipt selection."))
        if not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64:
            raise UserError(self.env._("Refresh the report before opening details."))
        report = self.get_report(options)
        if report["fingerprint"] != expected_fingerprint:
            raise UserError(self.env._("The report sources changed. Refresh the report."))
        row = next((item for item in report["rows"] if item["product_id"] == product_id), None)
        if row is None or not report["options"]["show_fifo_receipts"]:
            raise AccessError(self.env._("The requested product is unavailable."))
        receipt = next((
            item for item in row["fifo_receipts"][boundary]["receipts"]
            if item["move_id"] == move_id and (item["lot_id"] or 0) == lot_id
        ), None)
        if receipt is None:
            raise AccessError(self.env._("The requested FIFO receipt is unavailable."))
        document = self.env[receipt["document_model"]].browse(receipt["document_id"])
        document.check_access("read")
        return {
            "document_model": document._name,
            "document_id": document.id,
            "document_name": document.display_name,
        }

    @api.model
    def get_xlsx(self, options, expected_fingerprint):
        """Build the full authorized statement as an XLSX byte stream."""
        import xlsxwriter

        if not isinstance(expected_fingerprint, str) or len(expected_fingerprint) != 64:
            raise UserError(self.env._("Refresh the report before exporting."))
        report = self.get_report(options)
        if report["fingerprint"] != expected_fingerprint:
            raise UserError(self.env._("The report sources changed. Refresh the report."))
        output = BytesIO()
        book = xlsxwriter.Workbook(output, {
            "in_memory": True,
            "strings_to_formulas": False,
            "strings_to_urls": False,
        })
        sheet = book.add_worksheet("Stock turnover")
        header = book.add_format({"bold": True, "bg_color": "#DDEBF7"})
        money = book.add_format({"num_format": "#,##0.00"})
        quantity = book.add_format({"num_format": "#,##0.000"})
        text_format = book.add_format({"num_format": "@"})

        def safe_text(row, column, value, style=None):
            sheet.write_string(row, column, str(value or ""), style or text_format)

        safe_text(0, 0, self.env._("Product stock turnover statement"), header)
        safe_text(1, 0, self.env._("Company"))
        safe_text(1, 1, self.env["res.company"].browse(report["options"]["company_id"]).name)
        safe_text(2, 0, self.env._("Period"))
        safe_text(2, 1, report["options"]["date_from"] + " — " + report["options"]["date_to"])
        safe_text(3, 0, self.env._("Time zone"))
        safe_text(3, 1, report["timezone"])
        safe_text(4, 0, self.env._("Warehouse"))
        warehouse_id = report["options"]["warehouse_id"]
        safe_text(4, 1, self.env["stock.warehouse"].browse(warehouse_id).display_name if warehouse_id else "")
        safe_text(5, 0, self.env._("Location"))
        location_id = report["options"]["location_id"]
        safe_text(5, 1, self.env["stock.location"].browse(location_id).complete_name if location_id else "")
        safe_text(6, 0, self.env._("Include child locations"))
        safe_text(6, 1, self.env._("Yes") if report["options"]["include_children"] else self.env._("No"))
        safe_text(7, 0, self.env._("Currency"))
        safe_text(7, 1, report["currency_name"])
        safe_text(8, 0, self.env._("Effective cutoff (UTC)"))
        safe_text(8, 1, report["options"]["cutoff"])
        safe_text(9, 0, self.env._("Generated at (UTC)"))
        safe_text(9, 1, report["generated_at"])
        safe_text(10, 0, self.env._("Recorded history can be corrected; this statement uses its current edition."))

        columns = [
            ("default_code", self.env._("Reference")),
            ("name", self.env._("Product")),
            ("uom_name", self.env._("Unit")),
            ("closing_unit_cost", self.env._("Closing unit cost")),
            ("opening_qty", self.env._("Opening quantity")),
            ("opening_value", self.env._("Opening value")),
            ("incoming_qty", self.env._("Incoming quantity")),
            ("incoming_value", self.env._("Incoming value")),
            ("outgoing_qty", self.env._("Outgoing quantity")),
            ("outgoing_value", self.env._("Outgoing value")),
            ("valuation_difference", self.env._("Valuation difference")),
            ("closing_qty", self.env._("Closing quantity")),
            ("closing_value", self.env._("Closing value")),
            ("diagnostics", self.env._("Diagnostics")),
        ]
        show_fifo_receipts = report["options"]["show_fifo_receipts"]
        safe_text(11, 0, self.env._("Show FIFO receipts"))
        safe_text(11, 1, self.env._("Yes") if show_fifo_receipts else self.env._("No"))
        first_row = 12
        for column, (_key, label) in enumerate(columns):
            safe_text(first_row, column, label, header)
        for index, item in enumerate(report["rows"], start=first_row + 1):
            for column, (key, _label) in enumerate(columns):
                value = item[key]
                if key == "diagnostics":
                    safe_text(index, column, "; ".join(diag["message"] for diag in value))
                elif value is None:
                    safe_text(index, column, self.env._("Unavailable"))
                elif isinstance(value, (int, float)):
                    sheet.write_number(index, column, value, money if "value" in key or "cost" in key or "difference" in key else quantity)
                else:
                    safe_text(index, column, value)
        totals_row = first_row + 1 + len(report["rows"])
        safe_text(totals_row, 1, self.env._("Total"), header)
        for column, (key, _label) in enumerate(columns):
            if key in report["totals"]:
                sheet.write_number(totals_row, column, report["totals"][key], money)
        if report["totals"]["incomplete"]:
            safe_text(totals_row + 1, 1, self.env._("Monetary totals are incomplete."))
        unit_row = totals_row + 3
        for item in report["unit_totals"]:
            unit = self.env["uom.uom"].browse(item["uom_id"])
            safe_text(unit_row, 1, self.env._("Quantity totals: %s", unit.name))
            for column, (key, _label) in enumerate(columns):
                if key.endswith("_qty") and key in item:
                    sheet.write_number(unit_row, column, item[key], quantity)
            unit_row += 1
        sheet.freeze_panes(first_row + 1, 3)
        sheet.set_column(0, 0, 16)
        sheet.set_column(1, 1, 42)
        sheet.set_column(2, 12, 17)
        sheet.set_column(13, 13, 48)
        if show_fifo_receipts:
            fifo_sheet = book.add_worksheet("FIFO receipts")
            headers = [
                self.env._("Product"), self.env._("Boundary"), self.env._("Valuation scope"),
                self.env._("Date"), self.env._("Document"), self.env._("Unit"),
                self.env._("Unit cost"), self.env._("Remaining quantity"),
                self.env._("Remaining value"), self.env._("Valuation lot"),
            ]
            for column, label in enumerate(headers):
                fifo_sheet.write_string(0, column, label, header)
            line_number = 1
            for item in report["rows"]:
                for boundary in ("opening", "closing"):
                    basis = item["fifo_receipts"][boundary]
                    scope = self.env._("Company FIFO valuation basis")
                    if not basis["applicable"]:
                        fifo_sheet.write_string(line_number, 0, item["name"], text_format)
                        fifo_sheet.write_string(line_number, 1, boundary, text_format)
                        fifo_sheet.write_string(line_number, 2, self.env._("FIFO does not apply to this product."), text_format)
                        line_number += 1
                        continue
                    for receipt in basis["receipts"]:
                        for column, label in (
                            (0, item["name"]), (1, boundary), (2, scope),
                            (3, receipt["date"]), (4, receipt["document_name"]),
                            (5, item["uom_name"]), (9, receipt["lot_name"]),
                        ):
                            fifo_sheet.write_string(line_number, column, str(label or ""), text_format)
                        for column, value, style in (
                            (6, receipt["unit_cost"], money),
                            (7, receipt["quantity"], quantity),
                            (8, receipt["value"], money),
                        ):
                            fifo_sheet.write_number(line_number, column, value, style)
                        line_number += 1
                    if basis["diagnostics"]:
                        fifo_sheet.write_string(line_number, 0, item["name"], text_format)
                        fifo_sheet.write_string(line_number, 1, boundary, text_format)
                        fifo_sheet.write_string(line_number, 2, scope, text_format)
                        fifo_sheet.write_string(line_number, 4, "; ".join(basis["diagnostics"]), text_format)
                        fifo_sheet.write_number(line_number, 7, basis["unattributed_quantity"], quantity)
                        fifo_sheet.write_number(line_number, 8, basis["unattributed_value"], money)
                        line_number += 1
            fifo_sheet.freeze_panes(1, 0)
            fifo_sheet.set_column(0, 0, 42)
            fifo_sheet.set_column(1, 2, 29)
            fifo_sheet.set_column(3, 3, 20)
            fifo_sheet.set_column(4, 4, 48)
            fifo_sheet.set_column(5, 9, 20)
        book.close()
        return output.getvalue()
