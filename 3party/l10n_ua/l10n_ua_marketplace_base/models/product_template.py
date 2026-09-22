from odoo import api, fields, models, _


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    marketplace_published = fields.Boolean(
        string='Published on Marketplaces',
        default=False,
        help='Product is available for marketplace publishing',
    )
    marketplace_item_ids = fields.One2many(
        'marketplace.pricelist.item',
        'product_tmpl_id',
        string='Marketplace Items',
    )
    marketplace_item_count = fields.Integer(
        string='Marketplace Item Count',
        compute='_compute_marketplace_item_count',
    )
    marketplace_category_ids = fields.Many2many(
        'marketplace.category',
        'product_template_marketplace_category_rel',
        'product_tmpl_id',
        'category_id',
        string='Marketplace Categories',
        help='Default marketplace categories for this product',
    )

    def _compute_marketplace_item_count(self):
        for product in self:
            product.marketplace_item_count = len(product.marketplace_item_ids)

    def action_view_marketplace_items(self):
        """View marketplace pricelist items for this product."""
        self.ensure_one()
        return {
            'name': _('Marketplace Items'),
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.pricelist.item',
            'view_mode': 'list,form',
            'domain': [('product_tmpl_id', '=', self.id)],
            'context': {'default_product_tmpl_id': self.id},
        }

    def action_add_to_marketplace(self):
        """Wizard to add product to marketplace pricelist."""
        self.ensure_one()
        return {
            'name': _('Add to Marketplace'),
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.product.add.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_product_tmpl_id': self.id},
        }
