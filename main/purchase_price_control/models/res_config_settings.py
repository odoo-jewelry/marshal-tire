from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    purchase_default_markup = fields.Float(
        related="company_id.purchase_default_markup",
        readonly=False,
    )
    purchase_price_rounding = fields.Float(
        related="company_id.purchase_price_rounding",
        readonly=False,
    )
