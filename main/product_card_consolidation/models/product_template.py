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
