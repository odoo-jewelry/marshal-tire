import hashlib
import json
import math
from collections import defaultdict

from odoo import _, api, Command, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import SQL

from .history_audit import _HISTORY_KEY, _HISTORY_TOKEN
from .history_revision import touch_products


_OPERATIONAL = ("stock.move", "stock.move.line", "stock.quant", "purchase.order.line", "sale.order.line", "pos.order.line")
_PRESERVE = (
    "state", "date", "date_planned", "name", "product_uom", "product_uom_id", "product_uom_qty",
    "product_qty", "quantity", "qty", "price_unit", "discount", "tax_ids", "price_subtotal",
    "price_subtotal_incl", "price_total", "price_tax", "value", "total_cost", "is_total_cost_computed",
    "location_id", "location_dest_id", "owner_id", "lot_id", "package_id", "result_package_id",
    "picking_id", "purchase_line_id", "sale_line_id", "move_id", "order_id", "origin_returned_move_id",
    "refunded_orderline_id", "reserved_quantity", "in_date", "picked",
    "qty_received", "qty_delivered", "qty_invoiced", "technical_price_unit",
)


def snapshot(records, names=None):
    names = [name for name in (names or _PRESERVE) if name in records._fields]
    values = records.sorted("id").read(names)
    for row in values:
        for name in names:
            if records._fields[name].type == "many2one":
                row[name] = row[name][0] if row[name] else False
            elif records._fields[name].type in ("many2many", "one2many"):
                row[name] = sorted(row[name])
    return json.loads(json.dumps(values, default=str))


class ProductHistoryConsolidationService(models.AbstractModel):
    _inherit = "product.card.consolidation.service"

    @api.model
    def analyze(self, canonical, duplicate, mode="stock"):
        if mode == "stock":
            result = super().analyze(canonical, duplicate)
            if canonical.merged_source_ids:
                result["lines"].append(self._line("warning", "history_mode", 0, _(
                    "Current-stock consolidation keeps source history separate. Historical write-offs require full history conversion of every source."
                )))
            return result
        if mode != "history":
            raise UserError(_("Select a supported consolidation mode."))
        return self._history_analyze(canonical, duplicate)

    @api.model
    def _history_group(self, canonical, duplicate):
        canonical.ensure_one()
        duplicate.ensure_one()
        self._check_actor(canonical | duplicate)
        if canonical == duplicate or not canonical.active or canonical.merged_into_id:
            raise UserError(_("Select an active canonical card and a different duplicate."))
        if duplicate.merged_into_id and duplicate.merged_into_id != canonical:
            raise UserError(_("The source belongs to another canonical product."))
        sources = canonical.with_context(active_test=False).merged_source_ids | duplicate
        if any(source.merged_source_ids for source in sources):
            raise UserError(_("A source with its own absorbed cards requires separate review."))
        group = canonical | sources
        self._check_actor(group)
        return sources, group.with_context(active_test=False).product_variant_ids

    @api.model
    def _history_record_sets(self, products):
        return {name: self.env[name].sudo().with_context(active_test=False).search([
            ("product_id", "in", products.ids),
        ], order="id") for name in _OPERATIONAL if name in self.env}

    @api.model
    def _history_extra_blockers(self, canonical, sources, records):
        """Integration modules may validate their protected histories here."""
        return []

    @api.model
    def _history_extra_warnings(self, real):
        """Let integrations explain narrower downstream processing profiles."""
        return []

    @api.model
    def _history_unhandled_references(self, sources):
        products = sources.with_context(active_test=False).product_variant_ids
        configuration = {item["model"] for item in self._configuration_specs(sources[:1], sources[:1])}
        # These are immutable evidence or card/configuration relations, not live operations.
        evidence = {"product.value", "product.identifier.alias", "pos.cost.recompute", "pos.cost.recompute.line",
                    "pos.cost.recompute.stock.line", "product.product", "product.template",
                    "purchase.import.profile"}
        lines = []
        for name in sorted(self.env.registry.models):
            Model = self.env[name]
            if (name in _OPERATIONAL or name in configuration or name in evidence
                    or name.startswith("product.consolidation.") or not Model._auto or Model._transient):
                continue
            for field_name in Model._history_product_reference_fields():
                field = Model._fields[field_name]
                ids = products.ids if field.comodel_name == "product.product" else sources.ids
                linked = Model.sudo().with_context(active_test=False).search([(field_name, "in", ids)])
                if linked:
                    lines.append(self._line("blocker", "unhandled_reference", len(linked), _(
                        "Unsupported product references: %(model)s.%(field)s, records %(ids)s.",
                        model=name, field=field_name, ids=", ".join(map(str, linked.ids)),
                    )))
        return lines

    @api.model
    def _history_analyze(self, canonical, duplicate):
        # Finish existing deferred computations before capturing source versions.
        # Otherwise the first lock flush can invalidate an unchanged preview.
        self.env.flush_all()
        sources, products = self._history_group(canonical, duplicate)
        company = canonical.company_id or self.env.company
        group = canonical | sources
        blockers = []

        def block(category, message, count=1):
            blockers.append(self._line("blocker", category, count, message))

        for source in group:
            if len(source.with_context(active_test=False).product_variant_ids) != 1:
                block("variants", _("Each product card must have exactly one variant."))
            if (source.company_id != canonical.company_id or source.uom_id != canonical.uom_id
                    or source.type != canonical.type or source.is_storable != canonical.is_storable):
                block("identity", _("Company, unit and inventory identity must match: %s", source.display_name))
            if source.tracking != "none":
                block("tracking", _("Tracked products cannot be consolidated."))
        records = self._history_record_sets(products)
        moves = records["stock.move"]
        quants = records["stock.quant"]
        details = records["stock.move.line"]
        for name, rows in records.items():
            if "company_id" in rows._fields and rows.filtered(lambda row: row.company_id and row.company_id != company):
                block("company_history", _("History in another company prevents consolidation: %s", name))
        if self.env["stock.lot"].sudo().search_count([("product_id", "in", products.ids)]):
            block("tracking", _("Existing lots or serial numbers prevent consolidation."))
        if moves.filtered(lambda move: move.state not in ("done", "cancel")):
            block("open_moves", _("Complete or cancel all unfinished stock movements before merging history."))
        if quants.filtered(lambda q: q.reserved_quantity or q.inventory_quantity_set):
            block("reservations", _("Reservations or unfinished inventory counts prevent history consolidation."))
        if quants.filtered(lambda q: q.owner_id or q.lot_id) or details.filtered(lambda line: line.owner_id or line.lot_id):
            block("ownership", _("Tracked or third-party stock history is not supported."))
        if quants.filtered(lambda q: q.location_id.is_valued_internal and q.quantity < 0):
            block("negative_stock", _("Negative internal stock prevents history consolidation."))
        if moves:
            for product in products.with_company(company):
                if product.cost_method != "fifo" or product.valuation != "periodic" or not product.is_storable:
                    block("valuation", _("Full stock history requires FIFO and periodic valuation: %s", product.display_name))
            signatures = {self._valuation_signature(product, company) for product in products}
            if len(signatures) != 1:
                block("valuation", _("Stock valuation settings must match."))
        real = moves.filtered(lambda move: not move.consolidation_source_receipt_id)
        incoming_pairs = moves.filtered(lambda move: move.consolidation_source_receipt_id and move.state == "done")
        pairs = incoming_pairs | incoming_pairs.consolidation_out_move_id
        retired = moves.filtered("consolidation_retired_operation_id")
        real -= pairs | retired
        source_products = sources.with_context(active_test=False).product_variant_ids
        for incoming in incoming_pairs:
            outgoing, receipt = incoming.consolidation_out_move_id, incoming.consolidation_source_receipt_id
            if (not outgoing or outgoing not in moves or outgoing.state != "done"
                    or incoming.product_id != self._variant(canonical) or outgoing.product_id not in source_products
                    or receipt.product_id != outgoing.product_id or receipt.state != "done" or not receipt.is_in
                    or incoming.company_id != company or outgoing.company_id != company
                    or not incoming.is_inventory or not outgoing.is_inventory
                    or incoming.location_id.usage != "inventory" or outgoing.location_dest_id != incoming.location_id
                    or outgoing.location_id != incoming.location_dest_id
                    or incoming.product_uom != outgoing.product_uom
                    or incoming.product_uom.compare(incoming.quantity, outgoing.quantity)
                    or company.currency_id.compare_amounts(incoming.value, outgoing.value)
                    or incoming.origin_returned_move_id or outgoing.origin_returned_move_id
                    or incoming.move_orig_ids or incoming.move_dest_ids or outgoing.move_orig_ids or outgoing.move_dest_ids
                    or incoming.picking_id or outgoing.picking_id):
                block("old_pair", _("The previous consolidation transfer cannot be proven: %s", incoming.display_name))
        for move in pairs:
            if any(move[name] for name in ("cost_repair_line_id", "historical_cost_line_id") if name in move._fields):
                block("old_pair", _("A previously audited valuation prevents retiring transfer %s.", move.display_name))
        if len(pairs) != 2 * len(incoming_pairs):
            block("old_pair", _("Previous consolidation pairs are incomplete or share a movement."))
        for move in moves.filtered(lambda item: item.state == "done"):
            if move.account_move_id or move.analytic_account_line_ids:
                block("financial", _("Accounting or analytic links prevent rewriting movement %s.", move.display_name))
            if not math.isfinite(move.quantity) or move.quantity <= 0 or not math.isfinite(move.value):
                block("quantity", _("Invalid movement quantity or value: %s", move.display_name))
            if move.date > fields.Datetime.now():
                block("date", _("Future stock history requires separate review: %s", move.display_name))
            day = move.date.date()
            limits = [company._get_user_lock_date(key, ignore_exceptions=True) for key in (
                "fiscalyear_lock_date", "tax_lock_date", "sale_lock_date", "purchase_lock_date",
            )] + [company.user_hard_lock_date]
            closing = company.sudo()._get_last_closing_date()
            if any(limit and day <= limit for limit in limits) or (closing and day <= fields.Date.to_date(closing)):
                block("period", _("A locked or closed period prevents rewriting movement %s.", move.display_name))
            if move in real:
                usages = {move.location_id.usage, move.location_dest_id.usage}
                if not usages <= {"internal", "supplier", "customer", "inventory"}:
                    block("route", _("Unsupported stock route: %s", move.display_name))
                if move.origin_returned_move_id and move.origin_returned_move_id not in real:
                    block("return", _("The return source is outside the merged history: %s", move.display_name))
        dangling_returns = self.env["stock.move"].sudo().search([
            ("origin_returned_move_id", "in", moves.ids), ("id", "not in", moves.ids),
        ])
        if dangling_returns:
            block("return", _("Return movements outside this product history prevent consolidation."))
        if self.env["account.move.line"].sudo().search_count([("product_id", "in", products.ids)]):
            block("financial", _("Invoice or journal product lines prevent full history consolidation; review their linked documents first."))
        blockers += self._history_unhandled_references(sources)
        blockers += self._history_extra_blockers(canonical, sources, records)
        new_sources = sources.filtered(lambda source: not source.merged_into_id)
        configurations = []
        for source in new_sources:
            plan, conflicts = self._configuration_plan(canonical, source)
            configurations += plan
            blockers += conflicts + self._alias_blockers(canonical, source)
        balances = self._history_balances(moves.filtered(lambda move: move.state == "done"), by_product=True)
        quant_balances = defaultdict(float)
        for quant in quants:
            quant_balances[(quant.product_id.id, quant.location_id.id, quant.package_id.id)] += quant.quantity
        if any(not canonical.uom_id.is_zero(balances[key] - quant_balances[key])
               for key in balances.keys() | quant_balances.keys()):
            block("stock_reconciliation", _("Recorded movements do not reconcile with physical stock by location and package."))
        issues = real.filtered(lambda move: move.state == "done" and move.is_out)
        earliest = min(issues.mapped("date"), default=False)
        lines = blockers + [self._line("transfer", "full_history", len(real), _(
            "Original history will use the canonical product. Past product reports will change; run cost recomputation separately."
        ))]
        lines += [self._line("transfer", "source", 1, source.display_name) for source in sources]
        lines += [self._line("transfer", name, len(rows), _("Product references: %s", name))
                  for name, rows in records.items() if rows]
        if pairs:
            lines.append(self._line("transfer", "retire_pairs", len(pairs), _("Previous transfer pairs will leave active stock and FIFO, retaining their evidence.")))
        if earliest:
            lines.append(self._line("warning", "cost_start", len(issues), _("Manual costs must include issues from %s.", earliest), source_date=earliest))
        lines += self._history_extra_warnings(real.filtered(lambda move: move.state == "done"))
        combined = defaultdict(float)
        for (_product, location, package), quantity in quant_balances.items():
            combined[(location, package)] += quantity
        for (location, package), quantity in combined.items():
            if quantity:
                lines.append(self._line("transfer", "physical_stock", 1,
                    _("Combined physical stock after full consolidation."), quantity=quantity,
                    location_id=location, package_id=package))
        analysis = {"blockers": blockers, "lines": lines, "sources": sources, "products": products,
                    "records": records, "pairs": pairs, "real": real, "company": company,
                    "new_sources": new_sources, "configuration_plan": configurations,
                    "earliest": earliest, "quantities": dict(quant_balances)}
        # Derived display values (notably quant.value) are not source evidence:
        # their cache can be refreshed independently without any history mutation.
        evidence = {name: snapshot(rows, [field for field in ("write_date", "product_id", *_PRESERVE)
                                        if field in rows._fields and rows._fields[field].store])
                    for name, rows in records.items()}
        evidence.update(products=snapshot(products, ["consolidation_revision", "write_date", "categ_id"]),
                        cards=snapshot(group, ["write_date", "active", "merged_into_id"]),
                        company=snapshot(company, ["write_date"]),
                        configuration=[(action, row._name, row.id, str(row.write_date), target.id)
                                       for action, _spec, row, target in configurations])
        analysis["fingerprint"] = hashlib.sha256(json.dumps(evidence, sort_keys=True).encode()).hexdigest()
        return analysis

    @api.model
    def _history_balances(self, moves, by_product=False):
        result = defaultdict(float)
        for line in moves.move_line_ids:
            qty = line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
            prefix = (line.product_id.id,) if by_product else ()
            result[prefix + (line.location_id.id, line.package_id.id)] -= qty
            result[prefix + (line.location_dest_id.id, line.result_package_id.id)] += qty
        return result

    @api.model
    def consolidate(self, canonical, duplicate, expected_fingerprint=None, mode="stock"):
        if mode == "stock":
            return super().consolidate(canonical, duplicate, expected_fingerprint=expected_fingerprint)
        if mode != "history" or not expected_fingerprint:
            raise UserError(_("Review a full-history preview before confirmation."))
        self._check_actor(canonical | duplicate)
        previous = self.env["product.consolidation.operation"].search([
            ("canonical_id", "=", canonical.id), ("source_ids", "in", duplicate.id),
            ("fingerprint", "=", expected_fingerprint),
        ], limit=1)
        if previous:
            return canonical
        with self.env.cr.savepoint():
            plan = self._history_analyze(canonical, duplicate)
            locks = [plan["company"], canonical | plan["sources"], plan["products"], plan["products"].categ_id]
            locks += list(plan["records"].values())
            for records in locks:
                locked = records.sorted("id").try_lock_for_update()
                if set(locked.ids) != set(records.ids):
                    raise UserError(_("Another operation is changing this history. Refresh the preview."))
                records.invalidate_recordset()
            plan = self._history_analyze(canonical, duplicate)
            if plan["blockers"]:
                raise UserError("\n".join(line["message"] for line in plan["blockers"]))
            if plan["fingerprint"] != expected_fingerprint:
                raise UserError(_("The full-history preview is outdated. Review current history."))
            self.with_company(plan["company"])._history_apply(canonical.with_company(plan["company"]), plan)
        return canonical

    @api.model
    def _history_rewrite(self, records, canonical_product):
        if not records:
            return
        names = [name for name in _PRESERVE if name in records._fields]
        # Standard ORM deliberately forbids changing done movement products and
        # re-defaults commercial fields. This bounded identity migration changes
        # only reviewed product FKs, keeping original documents and business values.
        self.env.cr.execute(SQL("UPDATE %s SET product_id = %s WHERE id IN %s",
                                SQL.identifier(records._table), canonical_product.id, tuple(records.ids)))
        records.invalidate_recordset(["product_id"])
        records.modified(["product_id"])
        # Do not re-default explicitly preserved historical values from today's card.
        for name in names:
            field = records._fields[name]
            if field.store and field.compute:
                self.env.remove_to_compute(field, records)

    @api.model
    def _history_apply(self, canonical, plan):
        canonical_product = self._variant(canonical)
        sources, products, pairs = plan["sources"], plan["products"], plan["pairs"]
        source_products = sources.with_context(active_test=False).product_variant_ids
        line_values = []
        changes = {}
        invariants = {}
        self.env.flush_all()
        for name, records in plan["records"].items():
            changed = records.filtered(lambda row: row.product_id in source_products)
            if name in ("stock.move", "stock.move.line"):
                changed -= pairs if name == "stock.move" else pairs.move_line_ids
            for row, values in zip(changed.sorted("id"), snapshot(changed)):
                line_values.append(Command.create({"record_model": name, "record_id": row.id,
                    "record_label": row.display_name, "source_product_id": row.product_id.id,
                    "canonical_product_id": canonical_product.id, "kind": "identity", "before": values}))
            changes[name] = changed
            names = [field for field in _PRESERVE if field in records._fields and records._fields[field].store]
            invariants[name] = (names, snapshot(changed, names))
        # Stage every linked FK before flushing any dependent calculation. In
        # particular, PO received quantities must never see only half the merge.
        for changed in changes.values():
            self._history_rewrite(changed, canonical_product)
        for changed in changes.values():
            for name in _PRESERVE:
                field = changed._fields.get(name)
                if field and field.store and field.compute:
                    self.env.remove_to_compute(field, changed)
        self.env.flush_all()
        for name, changed in changes.items():
            fields_to_check, before = invariants[name]
            if snapshot(changed, fields_to_check) != before:
                raise UserError(_("Historical business values changed unexpectedly in %s. Nothing was applied.", name))
        for row, values in zip(pairs.sorted("id"), snapshot(pairs)):
            line_values.append(Command.create({"record_model": "stock.move", "record_id": row.id,
                "record_label": row.display_name, "source_product_id": row.product_id.id,
                "canonical_product_id": canonical_product.id, "kind": "retired", "before": values}))
        # Only proven synthetic pairs enter this path; real done moves never change state.
        pairs.with_context(**{_HISTORY_KEY: _HISTORY_TOKEN}).write({"state": "cancel"})
        for source in plan["new_sources"]:
            config, conflicts = self._configuration_plan(canonical, source)
            if conflicts:
                raise UserError("\n".join(line["message"] for line in conflicts))
            self._transfer_configuration(config)
            self._transfer_sets(canonical, source)
            self._transfer_project_configuration(canonical, source)
            self._create_aliases(canonical, source)
            source.sudo().with_context(product_consolidation_write=True).write({"merged_into_id": canonical.id})
            source.sudo().action_archive()
        touch_products(products)
        self._history_after_rewrite(canonical, plan)
        self.env.flush_all()
        for name, changed in changes.items():
            fields_to_check, before = invariants[name]
            if snapshot(changed, fields_to_check) != before:
                raise UserError(_("Historical business values changed unexpectedly in %s. Nothing was applied.", name))
        products.invalidate_recordset()
        current = self._history_record_sets(products)
        current["stock.quant"].invalidate_recordset(["value"])
        expected = defaultdict(float)
        for (_product, location, package), quantity in plan["quantities"].items():
            expected[(location, package)] += quantity
        actual = defaultdict(float)
        for quant in current["stock.quant"]:
            if quant.product_id != canonical_product and not quant.product_uom_id.is_zero(quant.quantity):
                raise UserError(_("Stock remains on an absorbed source."))
            actual[(quant.location_id.id, quant.package_id.id)] += quant.quantity
        calculated = self._history_balances(current["stock.move"].filtered(lambda move: move.state == "done"))
        if any(not canonical.uom_id.is_zero(expected[key] - actual[key])
               or not canonical.uom_id.is_zero(calculated[key] - actual[key])
               for key in expected.keys() | actual.keys() | calculated.keys()):
            raise UserError(_("Stock did not reconcile after full history consolidation."))
        operation = self.env["product.consolidation.operation"].with_context(**{_HISTORY_KEY: _HISTORY_TOKEN}).create({
            "company_id": plan["company"].id, "canonical_id": canonical.id,
            "source_ids": [Command.set(sources.ids)], "user_id": self.env.uid,
            "applied_at": fields.Datetime.now(), "reason": _("Full consolidation of duplicate product history"),
            "fingerprint": plan["fingerprint"], "earliest_issue_at": plan["earliest"], "line_ids": line_values,
            "quantities": {str(key): value for key, value in expected.items()},
        })
        pairs.with_context(**{_HISTORY_KEY: _HISTORY_TOKEN}).write({"consolidation_retired_operation_id": operation.id})
        canonical.message_post(body=_("Full product history consolidated. Audit operation: %s. Run cost recomputation separately.", operation.id))

    @api.model
    def _history_after_rewrite(self, canonical, plan):
        """Integration hook for revision invalidation; any failure rolls back the merge."""
