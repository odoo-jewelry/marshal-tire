from collections import defaultdict

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
    def _line(self, severity, category, count, message):
        return {
            "severity": severity,
            "category": category,
            "count": count,
            "message": message,
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
    def _stock_blockers(self, templates):
        variants = templates.with_context(active_test=False).product_variant_ids
        blockers = []
        if not variants:
            return blockers
        if self.env["stock.lot"].sudo().search_count([("product_id", "in", variants.ids)]):
            blockers.append(self._line("blocker", "tracking", 1, _("Existing lots or serial numbers prevent consolidation.")))
        quants = self.env["stock.quant"].sudo().search([("product_id", "in", variants.ids)])
        if any(
            not float_is_zero(quant.quantity, precision_rounding=quant.product_uom_id.rounding)
            or not float_is_zero(quant.reserved_quantity, precision_rounding=quant.product_uom_id.rounding)
            for quant in quants
        ):
            blockers.append(self._line("blocker", "stock", 1, _("On-hand or reserved quantity must be zero in every location.")))
        if any(quants.mapped("inventory_quantity_set")):
            blockers.append(self._line("blocker", "inventory_count", 1, _("An unfinished inventory count prevents consolidation.")))
        return blockers

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
    def analyze(self, canonical, duplicate):
        canonical.ensure_one()
        duplicate.ensure_one()
        self._check_actor(canonical | duplicate)
        blockers = self._base_blockers(canonical, duplicate)
        blockers += self._stock_blockers(canonical | duplicate)
        configuration_plan, configuration_blockers = self._configuration_plan(canonical, duplicate)
        blockers += configuration_blockers
        blockers += self._alias_blockers(canonical, duplicate)
        counts = defaultdict(int)
        for action, spec, _source, _target in configuration_plan:
            counts[(action, spec["category"])] += 1
        lines = blockers[:]
        for (action, category), count in counts.items():
            message = _("Configuration records will be transferred.") if action == "transfer" else _("Equivalent configuration records will be deduplicated.")
            lines.append(self._line("transfer", category, count, message))
        lines += self._draft_and_history_lines(canonical, duplicate)
        lines.append(self._line("preserve", "unknown_references", 0, _("Unlisted third-party references are outside the allowlist and will remain linked to the archived source card.")))
        lines.append(self._line("preserve", "canonical_values", 1, _("All scalar and company-dependent values of the canonical product will be preserved.")))
        return {
            "blockers": blockers,
            "lines": lines,
            "configuration_plan": configuration_plan,
        }

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
            "_transfer_configuration",
            "_transfer_sets",
            "_transfer_drafts",
            "_transfer_project_configuration",
        )

    @api.model
    def _run_consolidation_handler(self, handler_name, canonical, duplicate, analysis):
        if handler_name == "_transfer_configuration":
            return self._transfer_configuration(analysis["configuration_plan"])
        return getattr(self, handler_name)(canonical, duplicate)

    @api.model
    def consolidate(self, canonical, duplicate):
        canonical.ensure_one()
        duplicate.ensure_one()
        analysis = self.analyze(canonical, duplicate)
        if analysis["blockers"]:
            raise UserError("\n".join(line["message"] for line in analysis["blockers"]))
        canonical_admin = canonical.sudo().with_company(canonical.company_id or self.env.company)
        duplicate_admin = duplicate.sudo().with_company(canonical.company_id or self.env.company)
        for handler_name in self._consolidation_handler_registry():
            self._run_consolidation_handler(
                handler_name, canonical_admin, duplicate_admin, analysis
            )
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
        canonical_admin.message_post(body=Markup(_(
            "Product card %(source)s was consolidated into this card by %(user)s. "
            "Transferred/deduplicated records: %(transferred)s. Preserved references: %(preserved)s.",
            source=source_link,
            user=escape(self.env.user.display_name),
            transferred=transferred,
            preserved=preserved,
        )))
        return canonical
