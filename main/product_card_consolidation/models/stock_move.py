from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class StockMove(models.Model):
    _inherit = "stock.move"

    consolidation_source_receipt_id = fields.Many2one(
        "stock.move",
        string="Consolidation Source Receipt",
        copy=False,
        index=True,
        readonly=True,
        check_company=True,
        ondelete="restrict",
    )
    consolidation_source_date = fields.Datetime(
        string="Original Receipt Date",
        copy=False,
        readonly=True,
    )
    consolidation_out_move_id = fields.Many2one(
        "stock.move",
        string="Consolidation Outgoing Move",
        copy=False,
        index=True,
        readonly=True,
        check_company=True,
        ondelete="restrict",
    )

    @api.model
    def _consolidation_audit_field_names(self):
        return {
            "consolidation_source_receipt_id",
            "consolidation_source_date",
            "consolidation_out_move_id",
        }

    @api.model
    def _check_consolidation_audit_write(self, values_list):
        audit_fields = self._consolidation_audit_field_names()
        if any(audit_fields.intersection(values) for values in values_list) and not (
            self.env.context.get("product_consolidation_write")
            and self.env.user.has_group(
                "product_card_consolidation.group_product_consolidation_manager"
            )
        ):
            raise AccessError(
                _("Product consolidation audit fields can only be changed by consolidation.")
            )

    @api.model_create_multi
    def create(self, vals_list):
        self._check_consolidation_audit_write(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        self._check_consolidation_audit_write([vals])
        return super().write(vals)
