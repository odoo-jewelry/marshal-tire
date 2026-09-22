from odoo import api, fields, models, _


class MarketplaceCategory(models.Model):
    _name = 'marketplace.category'
    _description = 'Marketplace Category'
    _order = 'marketplace_type, parent_path'
    _parent_name = 'parent_id'
    _parent_store = True

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    marketplace_type = fields.Selection(
        selection='_selection_marketplace_type',
        string='Marketplace',
        required=True,
        index=True,
    )
    external_id = fields.Char(
        string='External ID',
        index=True,
        help='Category ID in marketplace system',
    )
    parent_id = fields.Many2one(
        'marketplace.category',
        string='Parent Category',
        index=True,
        ondelete='cascade',
    )
    parent_path = fields.Char(
        index=True,
    )
    child_ids = fields.One2many(
        'marketplace.category',
        'parent_id',
        string='Child Categories',
    )
    odoo_category_ids = fields.Many2many(
        'product.category',
        'marketplace_category_product_category_rel',
        'marketplace_category_id',
        'product_category_id',
        string='Odoo Categories',
        help='Map this marketplace category to Odoo product categories',
    )
    full_path = fields.Char(
        string='Full Path',
        compute='_compute_full_path',
        store=True,
        recursive=True,
    )
    active = fields.Boolean(
        default=True,
    )
    product_count = fields.Integer(
        string='Products',
        compute='_compute_product_count',
    )

    _external_marketplace_uniq = models.Constraint(
        'UNIQUE(external_id, marketplace_type)',
        'External ID must be unique per marketplace!',
    )

    @api.model
    def _selection_marketplace_type(self):
        """Return available marketplace types."""
        return [
            ('rozetka', 'Rozetka'),
            ('prom', 'Prom.ua'),
            ('epicentr', 'Epicentr'),
            ('allo', 'Allo'),
            ('hotline', 'Hotline'),
            ('priceua', 'Price.ua'),
        ]

    @api.depends('name', 'parent_id', 'parent_id.full_path')
    def _compute_full_path(self):
        for category in self:
            if category.parent_id:
                category.full_path = f"{category.parent_id.full_path} / {category.name}"
            else:
                category.full_path = category.name

    def _compute_product_count(self):
        for category in self:
            category.product_count = self.env['marketplace.pricelist.item'].search_count([
                ('marketplace_category_id', '=', category.id)
            ])

    @api.model
    def get_or_create(self, marketplace_type, external_id, name, parent_external_id=None):
        """Get existing category or create new one."""
        category = self.search([
            ('marketplace_type', '=', marketplace_type),
            ('external_id', '=', external_id),
        ], limit=1)

        if category:
            return category

        parent = False
        if parent_external_id:
            parent = self.search([
                ('marketplace_type', '=', marketplace_type),
                ('external_id', '=', parent_external_id),
            ], limit=1)

        return self.create({
            'name': name,
            'marketplace_type': marketplace_type,
            'external_id': external_id,
            'parent_id': parent.id if parent else False,
        })

    def name_get(self):
        result = []
        for category in self:
            result.append((category.id, category.full_path or category.name))
        return result

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=None, order=None):
        domain = domain or []
        if name:
            domain = ['|', ('name', operator, name), ('full_path', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)
