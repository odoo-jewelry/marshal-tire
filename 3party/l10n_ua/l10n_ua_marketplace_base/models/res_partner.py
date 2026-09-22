from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_marketplace_customer = fields.Boolean(
        string='Marketplace Customer',
        default=False,
        help='Customer was created from marketplace order',
    )
    marketplace_source = fields.Selection(
        selection=[
            ('rozetka', 'Rozetka'),
            ('prom', 'Prom.ua'),
            ('epicentr', 'Epicentr'),
            ('allo', 'Allo'),
        ],
        string='Marketplace Source',
    )
    marketplace_customer_id = fields.Char(
        string='Marketplace Customer ID',
        help='Customer ID in marketplace system',
    )
    marketplace_order_ids = fields.One2many(
        'marketplace.order',
        'partner_id',
        string='Marketplace Orders',
    )
    marketplace_order_count = fields.Integer(
        string='Marketplace Order Count',
        compute='_compute_marketplace_order_count',
    )

    def _compute_marketplace_order_count(self):
        for partner in self:
            partner.marketplace_order_count = len(partner.marketplace_order_ids)

    def action_view_marketplace_orders(self):
        """View marketplace orders for this partner."""
        self.ensure_one()
        return {
            'name': _('Marketplace Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.order',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }
