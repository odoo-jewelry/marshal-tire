from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_auto_invoice_company_customer = fields.Boolean(
        related="pos_config_id.auto_invoice_company_customer",
        readonly=False,
    )
