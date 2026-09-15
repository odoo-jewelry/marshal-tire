from collections import defaultdict
import hashlib

from markupsafe import Markup, escape

from odoo import _, Command, api, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_is_zero


class ProductCardConsolidationService(models.AbstractModel):
    _name = "product.card.consolidation.service"
    _description = "Product Card Consolidation Service"

    _manager_group = "product_card_consolidation.group_product_consolidation_manager"

    @api.model
    def _check_actor(self, templates):
        if not self.env.user.has_group(self._manager_group):
            raise AccessError(_("You are not allowed to consolidate product cards."))
        templates.check_access("read")
        companies = templates.mapped("company_id")
        if companies and companies - self.env.companies:
            raise AccessError(_("The product company is outside your allowed companies."))

    @api.model
    def _variant(self, template):
        variants = template.with_context(active_test=False).product_variant_ids
        return variants[:1]

    @api.model
    def _line(self, severity, category, count, message, **values):
        return {
            "severity": severity,
            "category": category,
            "count": count,
            "message": message,
            **values,
        }

    @api.model
    def _base_blockers(self, canonical, duplicate):
        blockers = []
        templates = canonical | duplicate
        if len(templates) != 2 or canonical == duplicate:
            return [self._line("blocker", "eligibility", 1, _("Select exactly two different product cards."))]
        if any(not template.active for template in templates):
            blockers.append(self._line("blocker", "eligibility", 1, _("Both product cards must be active.")))
        variant_counts = {
            template.id: len(template.with_context(active_test=False).product_variant_ids)
            for template in templates
        }
        if any(count != 1 for count in variant_counts.values()):
            blockers.append(self._line("blocker", "variants", 1, _("Each product card must have exactly one active or archived variant in total.")))
        if duplicate.merged_into_id:
            blockers.append(self._line("blocker", "lifecycle", 1, _("The duplicate was already consolidated.")))
        if duplicate.merged_source_ids:
            blockers.append(self._line("blocker", "lifecycle", 1, _("A previous canonical card cannot be used as the duplicate.")))
        if canonical.merged_into_id:
            blockers.append(self._line("blocker", "lifecycle", 1, _("A previously consolidated source cannot be canonical.")))
        if canonical.company_id != duplicate.company_id:
            blockers.append(self._line("blocker", "company", 1, _("Both product cards must have exactly the same company ownership.")))
        elif canonical.company_id and canonical.company_id not in self.env.companies:
            blockers.append(self._line("blocker", "company", 1, _("The product company is outside your allowed companies.")))
        if canonical.type != duplicate.type or canonical.is_storable != duplicate.is_storable:
            blockers.append(self._line("blocker", "product_type", 1, _("Product type and inventory tracking behavior must match.")))
        if canonical.uom_id != duplicate.uom_id:
            blockers.append(self._line("blocker", "uom", 1, _("Unit of measure must match.")))
        if canonical.tracking != "none" or duplicate.tracking != "none":
            blockers.append(self._line("blocker", "tracking", 1, _("Tracked products cannot be consolidated.")))
        return blockers

    @api.model
    def _internal_quants(self, variants, company):
        return self.env["stock.quant"].sudo().with_company(company).search([
            ("product_id", "in", variants.ids),
            ("company_id", "=", company.id),
            ("location_id.is_valued_internal", "=", True),
        ], order="product_id, location_id, package_id, id")

    @api.model
    def _stock_quantity(self, product, company):
        return sum(self._internal_quants(product, company).mapped("quantity"))

    @api.model
    def _valuation_signature(self, product, company):
        product = product.with_company(company)
        accounts = product._get_product_accounts()
        return (
            product.cost_method,
            product.valuation,
            product.property_stock_inventory.id,
            accounts.get("stock_valuation").id,
        )

    @api.model
    def _stock_transfer_analysis(self, canonical, duplicate):
        canonical_variant = self._variant(canonical)
        duplicate_variant = self._variant(duplicate)
        variants = canonical_variant | duplicate_variant
        blockers = []
        warnings = []
        plan = []
        if not variants:
            return {"blockers": blockers, "warnings": warnings, "plan": plan, "quant_ids": []}
        company = canonical.company_id or self.env.company
        if self.env["stock.lot"].sudo().search_count([("product_id", "in", variants.ids)]):
            blockers.append(self._line("blocker", "tracking", 1, _("Existing lots or serial numbers prevent consolidation.")))
        company_quants = self.env["stock.quant"].sudo().with_company(company).search([
            ("product_id", "in", variants.ids),
            ("company_id", "=", company.id),
        ])
        internal_quants = self._internal_quants(variants, company)
        other_company_internal = self.env["stock.quant"].sudo().search([
            ("product_id", "in", variants.ids),
            ("company_id", "!=", company.id),
            ("location_id.usage", "in", ("internal", "transit")),
            ("quantity", "!=", 0),
        ])
        if other_company_internal:
            blockers.append(self._line(
                "blocker", "company_stock", len(other_company_internal),
                _("Stock in another company prevents consolidation."),
            ))
        reserved = company_quants.filtered(
            lambda quant: not float_is_zero(
                quant.reserved_quantity,
                precision_rounding=quant.product_uom_id.rounding,
            )
        )
        if reserved:
            blockers.append(self._line(
                "blocker", "reservation", len(reserved),
                _("Reserved stock prevents consolidation."),
            ))
        negative = internal_quants.filtered(
            lambda quant: quant.product_uom_id.compare(quant.quantity, 0) < 0
        )
        if negative:
            blockers.append(self._line(
                "blocker", "negative_stock", len(negative),
                _("Negative internal stock prevents consolidation."),
            ))
        owned = internal_quants.filtered(
            lambda quant: quant.owner_id
            and quant.product_uom_id.compare(quant.quantity, 0) > 0
        )
        if owned:
            blockers.append(self._line(
                "blocker", "owner", len(owned),
                _("Owner-specific stock cannot be transferred by consolidation."),
            ))
        tracked = internal_quants.filtered(
            lambda quant: quant.lot_id
            and quant.product_uom_id.compare(quant.quantity, 0) > 0
        )
        if tracked:
            blockers.append(self._line(
                "blocker", "tracking", len(tracked),
                _("Lot or serial stock cannot be transferred by consolidation."),
            ))
        inventory_quants = company_quants.filtered("inventory_quantity_set")
        if inventory_quants:
            blockers.append(self._line("blocker", "inventory_count", 1, _("An unfinished inventory count prevents consolidation.")))
        open_moves = self.env["stock.move"].sudo().with_company(company).search([
            ("product_id", "=", duplicate_variant.id),
            ("company_id", "=", company.id),
            ("state", "not in", ("done", "cancel")),
        ])
        if open_moves:
            blockers.append(self._line(
                "blocker", "open_stock_moves", len(open_moves),
                _("Open stock movements for the duplicate must be completed or cancelled."),
            ))

        duplicate_quants = internal_quants.filtered(
            lambda quant: quant.product_id == duplicate_variant
            and not quant.owner_id
            and not quant.lot_id
            and quant.product_uom_id.compare(quant.quantity, 0) > 0
        )
        total_quantity = sum(duplicate_quants.mapped("quantity"))
        if duplicate_variant.uom_id.is_zero(total_quantity):
            return {
                "blockers": blockers,
                "warnings": warnings,
                "plan": plan,
                "quant_ids": internal_quants.ids,
            }

        if (
            canonical_variant.cost_method != "fifo"
            or duplicate_variant.cost_method != "fifo"
            or self._valuation_signature(canonical_variant, company)
            != self._valuation_signature(duplicate_variant, company)
            or not duplicate_variant.with_company(company).property_stock_inventory
        ):
            blockers.append(self._line(
                "blocker", "valuation", 1,
                _("Positive stock requires matching FIFO valuation, accounts, and inventory locations."),
            ))
            return {
                "blockers": blockers,
                "warnings": warnings,
                "plan": plan,
                "quant_ids": internal_quants.ids,
            }

        scoped_duplicate = duplicate_variant.with_company(company)
        remaining_by_product = scoped_duplicate._get_remaining_moves()
        remaining_by_move = remaining_by_product.get(scoped_duplicate, {})
        layers = []
        for source_move, remaining_quantity in remaining_by_move.items():
            if duplicate_variant.uom_id.compare(remaining_quantity, 0) <= 0:
                continue
            source_move = source_move.with_company(company)
            remaining_value = source_move.remaining_value
            layers.append({
                "source_move": source_move,
                "quantity": remaining_quantity,
                "value": remaining_value,
            })
            purchase_line = source_move.purchase_line_id
            if purchase_line and (
                not purchase_line.product_uom_id.is_zero(purchase_line.qty_to_invoice)
                or purchase_line.invoice_lines.filtered(
                    lambda line: line.move_id.state != "posted"
                )
            ):
                warnings.append(self._line(
                    "warning", "mutable_valuation", 1,
                    _("Source receipt valuation may still change after supplier billing."),
                    quantity=remaining_quantity,
                    value=remaining_value,
                    currency_id=company.currency_id.id,
                    source_move_id=source_move.id,
                    source_date=source_move.date,
                ))
        layer_quantity = sum(layer["quantity"] for layer in layers)
        if duplicate_variant.uom_id.compare(total_quantity, layer_quantity):
            blockers.append(self._line(
                "blocker", "stock_value_reconciliation", 1,
                _("Internal stock quantity does not match the remaining FIFO quantity."),
            ))
            return {
                "blockers": blockers,
                "warnings": warnings,
                "plan": plan,
                "quant_ids": internal_quants.ids,
            }
        layer_value = sum(layer["value"] for layer in layers)
        duplicate_variant.invalidate_recordset(["total_value"])
        if company.currency_id.compare_amounts(
            layer_value, duplicate_variant.total_value
        ):
            blockers.append(self._line(
                "blocker", "stock_value_reconciliation", 1,
                _("Remaining FIFO value does not match the duplicate inventory value."),
            ))
            return {
                "blockers": blockers,
                "warnings": warnings,
                "plan": plan,
                "quant_ids": internal_quants.ids,
            }

        layer_index = 0
        layer_quantity_left = layers[0]["quantity"] if layers else 0
        layer_value_left = layers[0]["value"] if layers else 0
        for quant in duplicate_quants.sorted(lambda item: (item.location_id.id, item.package_id.id, item.id)):
            quant_quantity_left = quant.quantity
            while duplicate_variant.uom_id.compare(quant_quantity_left, 0) > 0:
                layer = layers[layer_index]
                quantity = min(quant_quantity_left, layer_quantity_left)
                if duplicate_variant.uom_id.compare(quantity, layer_quantity_left) == 0:
                    value = layer_value_left
                else:
                    value = layer["value"] * quantity / layer["quantity"]
                plan.append({
                    "quant_id": quant.id,
                    "location_id": quant.location_id.id,
                    "package_id": quant.package_id.id,
                    "source_move_id": layer["source_move"].id,
                    "source_date": layer["source_move"].date,
                    "quantity": quantity,
                    "value": value,
                })
                quant_quantity_left -= quantity
                layer_quantity_left -= quantity
                layer_value_left -= value
                if duplicate_variant.uom_id.is_zero(layer_quantity_left):
                    layer_index += 1
                    if layer_index < len(layers):
                        layer_quantity_left = layers[layer_index]["quantity"]
                        layer_value_left = layers[layer_index]["value"]

        return {
            "blockers": blockers,
            "warnings": warnings,
            "plan": plan,
            "quant_ids": internal_quants.ids,
        }

    @api.model
    def _value(self, record, field_name):
        value = record[field_name]
        field = record._fields[field_name]
        if field.type == "many2one":
            return value.id
        if field.type in ("many2many", "one2many"):
            return tuple(sorted(value.ids))
        return value

    @api.model
    def _same_values(self, left, right, field_names):
        return all(self._value(left, name) == self._value(right, name) for name in field_names)

    @api.model
    def _configuration_specs(self, canonical, duplicate):
        canonical_variant = self._variant(canonical)
        duplicate_variant = self._variant(duplicate)
        return [
            {
                "category": "supplierinfo",
                "model": "product.supplierinfo",
                "source_domain": [("product_tmpl_id", "=", duplicate.id)],
                "target_domain": lambda record: [
                    ("product_tmpl_id", "=", canonical.id),
                    ("product_id", "=", canonical_variant.id if record.product_id else False),
                    ("partner_id", "=", record.partner_id.id),
                    ("product_code", "=", record.product_code),
                    ("product_name", "=", record.product_name),
                    ("product_uom_id", "=", record.product_uom_id.id),
                    ("min_qty", "=", record.min_qty),
                    ("company_id", "=", record.company_id.id),
                    ("currency_id", "=", record.currency_id.id),
                    ("date_start", "=", record.date_start),
                    ("date_end", "=", record.date_end),
                ],
                "compare": ("sequence", "price", "delay", "discount"),
                "values": lambda record: {
                    "product_tmpl_id": canonical.id,
                    "product_id": canonical_variant.id if record.product_id else False,
                },
            },
            {
                "category": "pricelist_rules",
                "model": "product.pricelist.item",
                "source_domain": [("product_tmpl_id", "=", duplicate.id)],
                "target_domain": lambda record: [
                    ("product_tmpl_id", "=", canonical.id),
                    ("product_id", "=", canonical_variant.id if record.product_id else False),
                    ("pricelist_id", "=", record.pricelist_id.id),
                    ("date_start", "=", record.date_start),
                    ("date_end", "=", record.date_end),
                    ("min_quantity", "=", record.min_quantity),
                ],
                "compare": (
                    "applied_on", "base", "base_pricelist_id", "compute_price",
                    "fixed_price", "percent_price", "price_discount", "price_round",
                    "price_surcharge", "price_min_margin", "price_max_margin",
                ),
                "values": lambda record: {
                    "product_tmpl_id": canonical.id,
                    "product_id": canonical_variant.id if record.product_id else False,
                },
            },
            {
                "category": "product_uoms",
                "model": "product.uom",
                "source_domain": [("product_id", "=", duplicate_variant.id)],
                "target_domain": lambda record: [
                    ("product_id", "=", canonical_variant.id),
                    ("barcode", "=", record.barcode),
                ],
                "compare": ("uom_id", "company_id"),
                "values": lambda _record: {"product_id": canonical_variant.id},
            },
            {
                "category": "orderpoints",
                "model": "stock.warehouse.orderpoint",
                "source_domain": [("product_id", "=", duplicate_variant.id)],
                "target_domain": lambda record: [
                    ("product_id", "=", canonical_variant.id),
                    ("location_id", "=", record.location_id.id),
                    ("company_id", "=", record.company_id.id),
                ],
                "compare": (
                    "trigger", "active", "warehouse_id", "product_min_qty",
                    "product_max_qty", "replenishment_uom_id", "route_id",
                ),
                "values": lambda _record: {"product_id": canonical_variant.id},
            },
            {
                "category": "putaway_rules",
                "model": "stock.putaway.rule",
                "source_domain": [("product_id", "=", duplicate_variant.id)],
                "target_domain": lambda record: [
                    ("product_id", "=", canonical_variant.id),
                    ("company_id", "=", record.company_id.id),
                    ("location_in_id", "=", record.location_in_id.id),
                ],
                "compare": (
                    "location_out_id", "sequence", "package_type_ids",
                    "storage_category_id", "active", "sublocation",
                ),
                "values": lambda _record: {"product_id": canonical_variant.id},
            },
            {
                "category": "storage_capacities",
                "model": "stock.storage.category.capacity",
                "source_domain": [("product_id", "=", duplicate_variant.id)],
                "target_domain": lambda record: [
                    ("product_id", "=", canonical_variant.id),
                    ("storage_category_id", "=", record.storage_category_id.id),
                ],
                "compare": ("quantity",),
                "values": lambda _record: {"product_id": canonical_variant.id},
            },
        ]

    @api.model
    def _configuration_plan(self, canonical, duplicate):
        plan = []
        blockers = []
        for spec in self._configuration_specs(canonical, duplicate):
            Model = self.env[spec["model"]].sudo().with_company(canonical.company_id or self.env.company)
            for source_record in Model.search(spec["source_domain"]):
                target_records = Model.search(spec["target_domain"](source_record))
                exact = target_records.filtered(
                    lambda target: self._same_values(source_record, target, spec["compare"])
                )
                if exact:
                    plan.append(("deduplicate", spec, source_record, exact[:1]))
                elif target_records:
                    blockers.append(self._line(
                        "blocker", spec["category"], 1,
                        _("Conflicting %(category)s configuration exists on the canonical product.", category=spec["category"]),
                    ))
                else:
                    plan.append(("transfer", spec, source_record, Model.browse()))
        return plan, blockers

    @api.model
    def _alias_blockers(self, canonical, duplicate):
        Alias = self.env["product.identifier.alias"].sudo().with_context(
            product_consolidation_write=True
        )
        Product = self.env["product.product"].sudo().with_context(active_test=False)
        canonical_variant = self._variant(canonical)
        duplicate_variant = self._variant(duplicate)
        blockers = []
        for identifier_type in ("default_code", "barcode"):
            values = {Alias._normalize_identifier(duplicate_variant[identifier_type])}
            values.update(Alias.search([
                ("product_id", "=", duplicate_variant.id),
                ("identifier_type", "=", identifier_type),
            ]).mapped("normalized_value"))
            for value in filter(None, values):
                if value == Alias._normalize_identifier(canonical_variant[identifier_type]):
                    continue
                aliases = Alias.search([
                    ("company_id", "=", canonical.company_id.id),
                    ("identifier_type", "=", identifier_type),
                    ("normalized_value", "=", value),
                    ("product_id", "not in", (canonical_variant | duplicate_variant).ids),
                ])
                direct = Product.search([
                    ("active", "=", True),
                    ("product_tmpl_id.company_id", "=", canonical.company_id.id),
                    (identifier_type, "=", value),
                    ("id", "not in", (canonical_variant | duplicate_variant).ids),
                ])
                if aliases or direct:
                    blockers.append(self._line("blocker", "identifiers", 1, _("Identifier %(value)s conflicts with another product.", value=value)))
        return blockers

    @api.model
    def _draft_and_history_lines(self, canonical, duplicate):
        duplicate_variant = self._variant(duplicate)
        lines = []
        editable_sale_lines = self.env["sale.order.line"].sudo().search([
            ("product_id", "=", duplicate_variant.id),
            ("state", "in", ("draft", "sent")),
        ]).filtered("product_updatable")
        editable_sale = len(editable_sale_lines)
        editable_purchase = self.env["purchase.order.line"].sudo().search_count([
            ("product_id", "=", duplicate_variant.id),
            ("state", "in", ("draft", "sent")),
        ])
        if editable_sale + editable_purchase:
            lines.append(self._line("transfer", "editable_documents", editable_sale + editable_purchase, _("Editable quotation and RFQ lines will use the canonical product.")))
        preserved_specs = [
            ("sale.order.line", [("product_id", "=", duplicate_variant.id), ("state", "not in", ("draft", "sent"))]),
            ("purchase.order.line", [("product_id", "=", duplicate_variant.id), ("state", "not in", ("draft", "sent"))]),
            ("account.move.line", [("product_id", "=", duplicate_variant.id)]),
            ("stock.move", [("product_id", "=", duplicate_variant.id)]),
            ("stock.move.line", [("product_id", "=", duplicate_variant.id)]),
            ("pos.order.line", [("product_id", "=", duplicate_variant.id)]),
        ]
        preserved = 0
        for model_name, domain in preserved_specs:
            if model_name in self.env:
                preserved += self.env[model_name].sudo().search_count(domain)
        lines.append(self._line("preserve", "history", preserved, _("Historical and operational references will remain linked to the archived source card.")))
        return lines

    @api.model
    def _analysis_fingerprint(self, canonical, duplicate, analysis):
        configuration_signature = tuple(
            (
                action,
                spec["category"],
                source.id,
                target.id,
            )
            for action, spec, source, target in analysis["configuration_plan"]
        )
        payload = (
            canonical.id,
            canonical.write_date,
            duplicate.id,
            duplicate.write_date,
            tuple(sorted(analysis["stock_quant_ids"])),
            self._stock_plan_signature(analysis["stock_plan"]),
            configuration_signature,
        )
        return hashlib.sha256(repr(payload).encode()).hexdigest()

    @api.model
    def analyze(self, canonical, duplicate):
        canonical.ensure_one()
        duplicate.ensure_one()
        self._check_actor(canonical | duplicate)
        blockers = self._base_blockers(canonical, duplicate)
        stock_analysis = self._stock_transfer_analysis(canonical, duplicate)
        blockers += stock_analysis["blockers"]
        configuration_plan, configuration_blockers = self._configuration_plan(canonical, duplicate)
        blockers += configuration_blockers
        blockers += self._alias_blockers(canonical, duplicate)
        counts = defaultdict(int)
        for action, spec, _source, _target in configuration_plan:
            counts[(action, spec["category"])] += 1
        lines = blockers[:]
        stock_plan = stock_analysis["plan"]
        if stock_plan:
            company = canonical.company_id or self.env.company
            lines.append(self._line(
                "transfer", "stock_transfer", len(stock_plan),
                _("Eligible stock will be transferred to the canonical product."),
                quantity=sum(segment["quantity"] for segment in stock_plan),
                value=sum(segment["value"] for segment in stock_plan),
                currency_id=company.currency_id.id,
            ))
            lines.extend(
                self._line(
                    "transfer", "stock_fifo_layer", 1,
                    _("A remaining FIFO layer will be transferred at its current value."),
                    quantity=segment["quantity"],
                    value=segment["value"],
                    currency_id=company.currency_id.id,
                    location_id=segment["location_id"],
                    package_id=segment["package_id"],
                    source_move_id=segment["source_move_id"],
                    source_date=segment["source_date"],
                )
                for segment in stock_plan
            )
        lines += stock_analysis["warnings"]
        for (action, category), count in counts.items():
            message = _("Configuration records will be transferred.") if action == "transfer" else _("Equivalent configuration records will be deduplicated.")
            lines.append(self._line("transfer", category, count, message))
        lines += self._draft_and_history_lines(canonical, duplicate)
        lines.append(self._line("preserve", "unknown_references", 0, _("Unlisted third-party references are outside the allowlist and will remain linked to the archived source card.")))
        lines.append(self._line("preserve", "canonical_values", 1, _("All scalar and company-dependent values of the canonical product will be preserved.")))
        analysis = {
            "blockers": blockers,
            "lines": lines,
            "configuration_plan": configuration_plan,
            "stock_plan": stock_plan,
            "stock_quant_ids": stock_analysis["quant_ids"],
        }
        analysis["fingerprint"] = self._analysis_fingerprint(
            canonical, duplicate, analysis
        )
        return analysis

    @api.model
    def _transfer_configuration(self, plan):
        for action, spec, source_record, _target in plan:
            if action == "deduplicate":
                source_record.unlink()
            else:
                source_record.write(spec["values"](source_record))

    @api.model
    def _transfer_sets(self, canonical, duplicate):
        for field_name in ("route_ids", "taxes_id", "supplier_taxes_id", "product_tag_ids"):
            if field_name in canonical._fields:
                canonical[field_name] = [Command.set((canonical[field_name] | duplicate[field_name]).ids)]
        canonical_variant = self._variant(canonical)
        duplicate_variant = self._variant(duplicate)
        if "additional_product_tag_ids" in canonical_variant._fields:
            canonical_variant.additional_product_tag_ids = [Command.set(
                (canonical_variant.additional_product_tag_ids | duplicate_variant.additional_product_tag_ids).ids
            )]
        if "optional_product_ids" in canonical._fields:
            canonical.optional_product_ids = [Command.set(
                ((canonical.optional_product_ids | duplicate.optional_product_ids) - duplicate).ids
            )]
            inbound = self.env["product.template"].sudo().search([
                ("optional_product_ids", "in", duplicate.id),
                ("id", "!=", canonical.id),
                ("company_id", "=", canonical.company_id.id),
            ])
            for template in inbound:
                template.optional_product_ids = [
                    Command.unlink(duplicate.id),
                    Command.link(canonical.id),
                ]

    @api.model
    def _transfer_drafts(self, canonical, duplicate):
        canonical_variant = self._variant(canonical)
        duplicate_variant = self._variant(duplicate)
        sale_lines = self.env["sale.order.line"].sudo().search([
            ("product_id", "=", duplicate_variant.id),
            ("state", "in", ("draft", "sent")),
            ("company_id", "=", canonical.company_id.id),
        ]).filtered("product_updatable")
        purchase_lines = self.env["purchase.order.line"].sudo().search([
            ("product_id", "=", duplicate_variant.id),
            ("state", "in", ("draft", "sent")),
            ("company_id", "=", canonical.company_id.id),
        ])
        for line in sale_lines:
            line.write({
                "product_id": canonical_variant.id,
                "product_template_id": canonical.id,
                "name": line.name,
                "product_uom_qty": line.product_uom_qty,
                "product_uom_id": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "tax_ids": [Command.set(line.tax_ids.ids)],
                "discount": line.discount,
            })
        for line in purchase_lines:
            line.write({
                "product_id": canonical_variant.id,
                "name": line.name,
                "product_qty": line.product_qty,
                "product_uom_id": line.product_uom_id.id,
                "price_unit": line.price_unit,
                "tax_ids": [Command.set(line.tax_ids.ids)],
                "discount": line.discount,
                "date_planned": line.date_planned,
            })

    @api.model
    def _transfer_project_configuration(self, canonical, duplicate):
        self.env["purchase.import.profile"].sudo().search([
            ("variant_template_id", "=", duplicate.id),
            ("company_id", "=", canonical.company_id.id),
        ]).write({"variant_template_id": canonical.id})

    @api.model
    def _stock_plan_signature(self, plan):
        return tuple(
            (
                segment["quant_id"],
                segment["location_id"],
                segment["package_id"],
                segment["source_move_id"],
                segment["source_date"],
                segment["quantity"],
                segment["value"],
            )
            for segment in plan
        )

    @api.model
    def _stock_move_values(
        self,
        product,
        quantity,
        location,
        inventory_location,
        package,
        outgoing,
        audit_values=None,
    ):
        source_location = location if outgoing else inventory_location
        destination_location = inventory_location if outgoing else location
        move_line_values = {
            "product_id": product.id,
            "product_uom_id": product.uom_id.id,
            "quantity": quantity,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "company_id": product.company_id.id or self.env.company.id,
            "picked": True,
        }
        if package:
            if outgoing:
                move_line_values["package_id"] = package.id
            else:
                move_line_values["result_package_id"] = package.id
        values = {
            "origin": _("Product card consolidation"),
            "product_id": product.id,
            "product_uom": product.uom_id.id,
            "product_uom_qty": quantity,
            "company_id": product.company_id.id or self.env.company.id,
            "location_id": source_location.id,
            "location_dest_id": destination_location.id,
            "is_inventory": True,
            "picked": True,
            "move_line_ids": [Command.create(move_line_values)],
        }
        if audit_values:
            values.update(audit_values)
        return values

    @api.model
    def _transfer_stock(self, canonical, duplicate, analysis):
        plan = analysis["stock_plan"]
        StockMove = self.env["stock.move"].sudo().with_context(
            product_consolidation_write=True
        )
        if not plan:
            return StockMove

        company = canonical.company_id or self.env.company
        canonical_variant = self._variant(canonical).with_company(company)
        duplicate_variant = self._variant(duplicate).with_company(company)
        Quant = self.env["stock.quant"].sudo().with_company(company)
        quants = Quant.browse(analysis["stock_quant_ids"]).sorted("id")
        locked_quants = quants.try_lock_for_update(allow_referencing=True)
        if set(locked_quants.ids) != set(quants.ids):
            raise UserError(_("Stock changed during consolidation. Refresh the preview and retry."))
        source_moves = StockMove.browse(
            sorted({segment["source_move_id"] for segment in plan})
        )
        locked_source_moves = source_moves.try_lock_for_update(allow_referencing=True)
        if set(locked_source_moves.ids) != set(source_moves.ids):
            raise UserError(_("Stock valuation changed during consolidation. Refresh and retry."))
        locked_quants.invalidate_recordset()
        locked_source_moves.invalidate_recordset()
        current = self._stock_transfer_analysis(canonical, duplicate)
        if current["blockers"] or self._stock_plan_signature(current["plan"]) != self._stock_plan_signature(plan):
            messages = [line["message"] for line in current["blockers"]]
            messages.append(_("Stock changed during consolidation. Refresh the preview and retry."))
            raise UserError("\n".join(dict.fromkeys(messages)))

        canonical_quantity_before = self._stock_quantity(canonical_variant, company)
        duplicate_quantity_before = self._stock_quantity(duplicate_variant, company)
        canonical_value_before = canonical_variant.total_value
        duplicate_value_before = duplicate_variant.total_value
        inventory_location = duplicate_variant.property_stock_inventory
        created_moves = StockMove

        for segment in plan:
            location = self.env["stock.location"].browse(segment["location_id"])
            package = self.env["stock.package"].browse(segment["package_id"])
            source_move = StockMove.browse(segment["source_move_id"])
            out_move = StockMove.create(self._stock_move_values(
                duplicate_variant,
                segment["quantity"],
                location,
                inventory_location,
                package,
                outgoing=True,
            ))
            out_move._action_done()
            if out_move.state != "done":
                raise UserError(_("The duplicate stock movement could not be completed."))
            if company.currency_id.compare_amounts(out_move.value, segment["value"]):
                raise UserError(_("The consumed FIFO value changed during consolidation."))

            in_values = self._stock_move_values(
                canonical_variant,
                segment["quantity"],
                location,
                inventory_location,
                package,
                outgoing=False,
                audit_values={
                    "consolidation_source_receipt_id": source_move.id,
                    "consolidation_source_date": segment["source_date"],
                    "consolidation_out_move_id": out_move.id,
                    "value_manual": out_move.value,
                },
            )
            in_move = StockMove.create(in_values)
            in_move._action_done()
            if in_move.state != "done":
                raise UserError(_("The canonical stock movement could not be completed."))
            if company.currency_id.compare_amounts(in_move.value, out_move.value):
                raise UserError(_("The incoming FIFO value does not match the outgoing value."))
            created_moves |= out_move | in_move

        canonical_variant.invalidate_recordset()
        duplicate_variant.invalidate_recordset()
        canonical_quantity_after = self._stock_quantity(canonical_variant, company)
        duplicate_quantity_after = self._stock_quantity(duplicate_variant, company)
        transferred_quantity = sum(segment["quantity"] for segment in plan)
        if not duplicate_variant.uom_id.is_zero(duplicate_quantity_after):
            raise UserError(_("The duplicate still has internal stock after consolidation."))
        if duplicate_variant.uom_id.compare(
            duplicate_quantity_before, transferred_quantity
        ) or canonical_variant.uom_id.compare(
            canonical_quantity_after,
            canonical_quantity_before + transferred_quantity,
        ):
            raise UserError(_("Stock quantities do not reconcile after consolidation."))
        total_value_before = canonical_value_before + duplicate_value_before
        total_value_after = canonical_variant.total_value + duplicate_variant.total_value
        if company.currency_id.compare_amounts(total_value_after, total_value_before):
            raise UserError(_("Inventory value does not reconcile after consolidation."))
        if any(move.state != "done" for move in created_moves):
            raise UserError(_("All consolidation stock movements must be completed."))
        if any(
            not move.consolidation_out_move_id
            for move in created_moves.filtered("consolidation_source_receipt_id")
        ):
            raise UserError(_("Consolidation stock movement audit links are incomplete."))
        return created_moves

    @api.model
    def _create_aliases(self, canonical, duplicate):
        Alias = self.env["product.identifier.alias"].sudo().with_context(
            product_consolidation_write=True
        )
        canonical_variant = self._variant(canonical)
        duplicate_variant = self._variant(duplicate)
        existing_source_aliases = Alias.search([("product_id", "=", duplicate_variant.id)])
        existing_source_aliases.write({"product_id": canonical_variant.id})
        values_list = []
        for identifier_type in ("default_code", "barcode"):
            value = Alias._normalize_identifier(duplicate_variant[identifier_type])
            if not value or value == Alias._normalize_identifier(canonical_variant[identifier_type]):
                continue
            if Alias.search_count([
                ("company_id", "=", canonical.company_id.id),
                ("identifier_type", "=", identifier_type),
                ("normalized_value", "=", value),
                ("product_id", "=", canonical_variant.id),
            ]):
                continue
            values_list.append({
                "product_id": canonical_variant.id,
                "source_product_id": duplicate_variant.id,
                "identifier_type": identifier_type,
                "value": value,
                "company_id": canonical.company_id.id,
            })
        if values_list:
            Alias.create(values_list)

    @api.model
    def _consolidation_after_handlers_hook(self, canonical, duplicate):
        """Extension/test hook executed before aliases and lifecycle writes."""

    @api.model
    def _consolidation_handler_registry(self):
        """Explicit extensibility point; never use generic foreign-key rewrites."""
        return (
            "_transfer_stock",
            "_transfer_configuration",
            "_transfer_sets",
            "_transfer_drafts",
            "_transfer_project_configuration",
        )

    @api.model
    def _run_consolidation_handler(self, handler_name, canonical, duplicate, analysis):
        if handler_name == "_transfer_stock":
            return self._transfer_stock(canonical, duplicate, analysis)
        if handler_name == "_transfer_configuration":
            return self._transfer_configuration(analysis["configuration_plan"])
        return getattr(self, handler_name)(canonical, duplicate)

    @api.model
    def consolidate(self, canonical, duplicate, expected_fingerprint=None):
        canonical.ensure_one()
        duplicate.ensure_one()
        analysis = self.analyze(canonical, duplicate)
        if analysis["blockers"]:
            raise UserError("\n".join(line["message"] for line in analysis["blockers"]))
        if (
            expected_fingerprint
            and analysis["fingerprint"] != expected_fingerprint
        ):
            raise UserError(_("The consolidation preview is outdated. Refresh it and review the current stock plan."))
        canonical_admin = canonical.sudo().with_company(canonical.company_id or self.env.company)
        duplicate_admin = duplicate.sudo().with_company(canonical.company_id or self.env.company)
        stock_moves = self.env["stock.move"]
        for handler_name in self._consolidation_handler_registry():
            result = self._run_consolidation_handler(
                handler_name, canonical_admin, duplicate_admin, analysis
            )
            if handler_name == "_transfer_stock":
                stock_moves |= result
        self._consolidation_after_handlers_hook(canonical_admin, duplicate_admin)
        self._create_aliases(canonical_admin, duplicate_admin)
        duplicate_admin.with_context(product_consolidation_write=True).write({
            "merged_into_id": canonical_admin.id,
        })
        duplicate_admin.action_archive()
        transferred = sum(
            line["count"] for line in analysis["lines"] if line["severity"] == "transfer"
        )
        preserved = sum(
            line["count"] for line in analysis["lines"] if line["severity"] == "preserve"
        )
        source_link = Markup('<a href="/web#id=%s&amp;model=product.template&amp;view_type=form">%s</a>') % (
            duplicate_admin.id,
            escape(duplicate_admin.display_name),
        )
        body = Markup(_(
            "Product card %(source)s was consolidated into this card by %(user)s. "
            "Transferred/deduplicated records: %(transferred)s. Preserved references: %(preserved)s.",
            source=source_link,
            user=escape(self.env.user.display_name),
            transferred=transferred,
            preserved=preserved,
        ))
        if stock_moves:
            move_links = Markup(", ").join(
                Markup('<a href="/web#id=%s&amp;model=stock.move&amp;view_type=form">%s</a>') % (
                    move.id,
                    escape(move.display_name),
                )
                for move in stock_moves
            )
            body += Markup("<br/>") + Markup(_(
                "Stock transfer movements: %(moves)s.", moves=move_links
            ))
        canonical_admin.message_post(body=body)
        return canonical
