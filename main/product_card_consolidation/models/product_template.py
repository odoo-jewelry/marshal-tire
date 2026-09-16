from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    merged_into_id = fields.Many2one(
        "product.template",
        string="Consolidated Into",
        copy=False,
        index=True,
        readonly=True,
        ondelete="restrict",
    )
    merged_source_ids = fields.One2many(
        "product.template",
        "merged_into_id",
        string="Absorbed Product Cards",
        context={"active_test": False},
        copy=False,
        readonly=True,
    )
    merged_source_count = fields.Integer(compute="_compute_merged_source_count")

    @api.depends("merged_source_ids")
    def _compute_merged_source_count(self):
        for template in self:
            template.merged_source_count = len(template.merged_source_ids)

    @api.constrains("merged_into_id")
    def _check_merged_into_id(self):
        for template in self:
            seen = template
            current = template.merged_into_id
            while current:
                if current == seen:
                    raise ValidationError(_("Product consolidation links cannot contain a cycle."))
                current = current.merged_into_id

    def write(self, vals):
        if "merged_into_id" in vals and not self.env.context.get(
            "product_consolidation_write"
        ):
            raise AccessError(_("Consolidation links can only be changed by the consolidation action."))
        if vals.get("active") and any(self.mapped("merged_into_id")):
            raise ValidationError(_("A consolidated product card cannot be unarchived."))
        return super().write(vals)

    def action_consolidate_into(self, canonical):
        self.ensure_one()
        canonical.ensure_one()
        return self.env["product.card.consolidation.service"].consolidate(
            canonical, self
        )

    def action_open_merged_sources(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Absorbed Product Cards"),
            "res_model": "product.template",
            "view_mode": "list,form",
            "domain": [("merged_into_id", "=", self.id)],
            "context": {"active_test": False, "create": False},
        }

    def _full_history_operations(self, company):
        self.ensure_one()
        return self.env["product.consolidation.operation"].sudo().with_context(active_test=False).search([
            ("canonical_id", "=", self.id), ("company_id", "=", company.id),
        ])

    def _has_full_consolidation_history(self, company):
        self.ensure_one()
        sources = self.with_context(active_test=False).merged_source_ids
        if self.merged_into_id or not sources:
            return False
        operations = self._full_history_operations(company)
        if sources - operations.source_ids:
            return False
        source_products = sources.with_context(active_test=False).product_variant_ids
        # New references to an archived source invalidate the proof as well as
        # newly absorbed cards; a prior successful audit alone is insufficient.
        return not self.env["stock.move"].sudo().search_count([
            ("product_id", "in", source_products.ids), ("state", "!=", "cancel"),
        ]) and not self.env["stock.quant"].sudo().search_count([
            ("product_id", "in", source_products.ids), ("quantity", "!=", 0),
        ])

    def action_open_history_consolidation(self):
        self.ensure_one()
        canonical = self.merged_into_id or self
        source = self if self.merged_into_id else self.with_context(active_test=False).merged_source_ids[:1]
        if not source:
            raise ValidationError(_("Select the canonical and duplicate cards from the product list."))
        return {
            "type": "ir.actions.act_window", "name": _("Full History Consolidation"),
            "res_model": "product.consolidation.wizard", "view_mode": "form", "target": "new",
            "context": {"active_test": False, "default_mode": "history",
                        "default_product_template_ids": (canonical | source).ids,
                        "default_canonical_template_id": canonical.id},
        }

    def action_open_history_consolidation_audit(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("History Consolidations"),
            "res_model": "product.consolidation.operation", "view_mode": "list,form",
            "domain": ["|", ("canonical_id", "=", self.id), ("source_ids", "in", self.id)],
        }
