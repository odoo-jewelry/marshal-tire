from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    last_purchase_price = fields.Float(
        string="Last Purchase Price",
        company_dependent=True,
        min_display_digits="Product Price",
        help="Last tax-included and discounted purchase price in the company currency per product unit.",
    )
