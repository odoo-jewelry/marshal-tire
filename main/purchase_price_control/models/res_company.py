from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = "res.company"

    purchase_default_markup = fields.Float(
        string="Default Purchase Markup (%)",
        default=0.0,
    )
    purchase_price_rounding = fields.Float(
        string="Purchase Sales Price Rounding",
        default=0.01,
        digits=(16, 4),
    )

    @api.constrains("purchase_price_rounding")
    def _check_purchase_price_rounding(self):
        if any(company.purchase_price_rounding <= 0 for company in self):
            raise ValidationError(self.env._("The purchase sales price rounding step must be positive."))
