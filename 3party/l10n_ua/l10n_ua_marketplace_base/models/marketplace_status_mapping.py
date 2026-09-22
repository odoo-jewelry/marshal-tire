from odoo import api, fields, models, _


class MarketplaceStatusMapping(models.Model):
    _name = 'marketplace.status.mapping'
    _description = 'Marketplace Status Mapping'
    _order = 'backend_id, sequence, internal_state'

    backend_id = fields.Many2one(
        'marketplace.backend',
        string='Backend',
        required=True,
        ondelete='cascade',
        index=True,
    )
    marketplace_type = fields.Selection(
        related='backend_id.marketplace_type',
        store=True,
        index=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    # External marketplace status
    external_code = fields.Char(
        string='Marketplace Code',
        required=True,
        help='Status code from marketplace API (e.g., "pending", "1")',
    )
    external_name = fields.Char(
        string='Marketplace Name',
        help='Display name of status from marketplace',
    )

    # Internal Odoo status
    internal_state = fields.Selection(
        selection=[
            ('new', 'New'),
            ('processing', 'Processing'),
            ('confirmed', 'Confirmed'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled'),
            ('returned', 'Returned'),
        ],
        string='Odoo State',
        required=True,
    )

    # Sync direction controls
    sync_to_marketplace = fields.Boolean(
        string='Push to Marketplace',
        default=True,
        help='When Odoo state changes, send this status to marketplace',
    )
    sync_from_marketplace = fields.Boolean(
        string='Pull from Marketplace',
        default=True,
        help='When marketplace sends this status, update Odoo state',
    )

    active = fields.Boolean(
        default=True,
    )

    _external_code_uniq = models.Constraint(
        'UNIQUE(backend_id, external_code)',
        'External code must be unique per backend!',
    )

    def name_get(self):
        result = []
        for mapping in self:
            name = f"{mapping.external_code}"
            if mapping.external_name:
                name = f"{mapping.external_name} ({mapping.external_code})"
            result.append((mapping.id, name))
        return result


class MarketplacePaymentStatus(models.Model):
    _name = 'marketplace.payment.status'
    _description = 'Marketplace Payment Status'
    _order = 'marketplace_type, sequence'

    marketplace_type = fields.Selection(
        selection=[
            ('rozetka', 'Rozetka'),
            ('prom', 'Prom.ua'),
            ('epicentr', 'Epicentr'),
            ('allo', 'Allo'),
        ],
        string='Marketplace',
        required=True,
        index=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    code = fields.Char(
        string='Status Code',
        required=True,
        help='Payment status code from marketplace API',
    )
    name = fields.Char(
        string='Status Name',
        required=True,
        translate=True,
    )
    is_paid = fields.Boolean(
        string='Marks as Paid',
        default=False,
        help='If True, this status means the order is paid',
    )
    is_pending = fields.Boolean(
        string='Payment Pending',
        default=False,
        help='If True, this status means payment is awaiting confirmation',
    )
    is_failed = fields.Boolean(
        string='Payment Failed',
        default=False,
        help='If True, this status means payment has failed',
    )

    active = fields.Boolean(
        default=True,
    )

    _payment_code_uniq = models.Constraint(
        'UNIQUE(marketplace_type, code)',
        'Payment status code must be unique per marketplace!',
    )

    def name_get(self):
        result = []
        for status in self:
            name = f"{status.name} ({status.code})"
            result.append((status.id, name))
        return result
