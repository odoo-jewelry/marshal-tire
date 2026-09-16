from odoo import _, api, fields, models
from odoo.exceptions import AccessError


_HISTORY_TOKEN = object()
_HISTORY_KEY = "product_history_consolidation_internal"


def history_internal(env):
    return env.context.get(_HISTORY_KEY) is _HISTORY_TOKEN


class ProductConsolidationOperation(models.Model):
    _name = "product.consolidation.operation"
    _description = "Full Product History Consolidation"
    _order = "id desc"
    _rec_name = "canonical_id"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", required=True, readonly=True, index=True)
    canonical_id = fields.Many2one("product.template", required=True, readonly=True, check_company=True, ondelete="restrict")
    source_ids = fields.Many2many("product.template", string="Absorbed Sources", readonly=True,
                                 check_company=True, context={"active_test": False})
    user_id = fields.Many2one("res.users", required=True, readonly=True, ondelete="restrict")
    applied_at = fields.Datetime(required=True, readonly=True)
    reason = fields.Text(required=True, readonly=True)
    fingerprint = fields.Char(required=True, readonly=True, index=True)
    earliest_issue_at = fields.Datetime(readonly=True)
    line_ids = fields.One2many("product.consolidation.operation.line", "operation_id", readonly=True)
    quantities = fields.Json(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not history_internal(self.env):
            raise AccessError(_("Consolidation evidence is created only by the reviewed operation."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Applied consolidation evidence cannot be changed."))

    def unlink(self):
        raise AccessError(_("Applied consolidation evidence cannot be deleted."))

    def copy_data(self, default=None):
        raise AccessError(_("Applied consolidation evidence cannot be copied."))

    def action_open_product(self):
        self.ensure_one()
        self.check_access("read")
        return {"type": "ir.actions.act_window", "res_model": "product.template",
                "res_id": self.canonical_id.id, "view_mode": "form"}


class ProductConsolidationOperationLine(models.Model):
    _name = "product.consolidation.operation.line"
    _description = "Product History Consolidation Evidence"
    _order = "id"
    _check_company_auto = True

    operation_id = fields.Many2one("product.consolidation.operation", required=True, readonly=True, ondelete="restrict")
    company_id = fields.Many2one(related="operation_id.company_id", store=True, index=True)
    source_product_id = fields.Many2one("product.product", readonly=True, ondelete="restrict", check_company=True)
    canonical_product_id = fields.Many2one("product.product", readonly=True, ondelete="restrict", check_company=True)
    record_model = fields.Char(required=True, readonly=True)
    record_id = fields.Integer(required=True, readonly=True)
    record_label = fields.Char(readonly=True)
    kind = fields.Selection([("identity", "Product Identity"), ("retired", "Retired Transfer")], required=True, readonly=True)
    before = fields.Json(readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not history_internal(self.env):
            raise AccessError(_("Consolidation evidence is created only by the reviewed operation."))
        return super().create(vals_list)

    def write(self, vals):
        raise AccessError(_("Applied consolidation evidence cannot be changed."))

    def unlink(self):
        raise AccessError(_("Applied consolidation evidence cannot be deleted."))

    def copy_data(self, default=None):
        raise AccessError(_("Applied consolidation evidence cannot be copied."))
