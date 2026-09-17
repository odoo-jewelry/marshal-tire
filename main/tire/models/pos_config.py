from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    auto_invoice_company_customer = fields.Boolean(
        string="Automatically enable invoicing for company customers",
        default=False,
        help="Enable the invoice option when selecting a company customer. "
        "When disabled, invoicing can still be selected manually. "
        "Reload the POS interface after changing this setting.",
    )
