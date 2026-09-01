from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    pos_short_name = fields.Char(string="Abbreviation", translate=True)
    uktzed_code = fields.Char(string="UKTZED Code")

    def _load_pos_data_fields(self, config):
        return [*super()._load_pos_data_fields(config), "pos_short_name"]
