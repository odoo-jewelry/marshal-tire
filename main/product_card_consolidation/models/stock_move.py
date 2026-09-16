from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from .history_audit import history_internal


class StockMove(models.Model):
    _inherit = "stock.move"

    consolidation_retired_operation_id = fields.Many2one(
        "product.consolidation.operation", string="History Conversion", readonly=True,
        copy=False, index=True, check_company=True, ondelete="restrict",
    )

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
        if (any("consolidation_retired_operation_id" in vals for vals in vals_list)
                or self.env.context.get("default_consolidation_retired_operation_id")) and not history_internal(self.env):
            raise AccessError(_("Retired transfers are managed by history consolidation."))
        self._check_consolidation_audit_write(vals_list)
        return super().create(vals_list)

    def write(self, vals):
        if ("consolidation_retired_operation_id" in vals or self.filtered("consolidation_retired_operation_id")) and not history_internal(self.env):
            raise AccessError(_("Retired consolidation transfers cannot be changed."))
        self._check_consolidation_audit_write([vals])
        return super().write(vals)

    def unlink(self):
        if self.filtered("consolidation_retired_operation_id"):
            raise AccessError(_("Retired consolidation transfers cannot be deleted."))
        return super().unlink()


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.model_create_multi
    def create(self, vals_list):
        move_ids = {vals.get("move_id", self.env.context.get("default_move_id")) for vals in vals_list}
        if self.env["stock.move"].browse(list(move_ids - {None, False})).filtered("consolidation_retired_operation_id"):
            raise AccessError(_("Retired consolidation transfers cannot be changed."))
        return super().create(vals_list)

    def write(self, vals):
        moves = self.move_id | self.env["stock.move"].browse(vals.get("move_id", []))
        if moves.filtered("consolidation_retired_operation_id") and not history_internal(self.env):
            raise AccessError(_("Retired consolidation transfers cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if self.move_id.filtered("consolidation_retired_operation_id"):
            raise AccessError(_("Retired consolidation transfers cannot be deleted."))
        return super().unlink()
