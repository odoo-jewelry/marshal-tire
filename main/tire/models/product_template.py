from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    uktzed_code = fields.Char(string="UKTZED Code")
