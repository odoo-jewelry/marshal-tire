from odoo import api, fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    ua_carrier_type = fields.Selection(
        selection=[
            ('novaposhta', 'Nova Poshta'),
            ('meest', 'Meest'),
            ('ukrposhta', 'Ukrposhta'),
        ],
        string='UA Carrier Type',
    )
    ua_api_key = fields.Char(
        string='API Key',
    )
    ua_sender_ref = fields.Char(
        string='Sender Reference',
        help='Sender reference ID in carrier system',
    )
    ua_sender_address_ref = fields.Char(
        string='Sender Address Reference',
    )
    ua_sender_contact_ref = fields.Char(
        string='Sender Contact Reference',
    )
    ua_default_service_type = fields.Selection(
        selection=[
            ('warehouse', 'Warehouse to Warehouse'),
            ('doors', 'Warehouse to Doors'),
            ('doors_warehouse', 'Doors to Warehouse'),
            ('doors_doors', 'Doors to Doors'),
        ],
        string='Default Service Type',
        default='warehouse',
    )
    ua_default_payment_method = fields.Selection(
        selection=[
            ('sender', 'Sender Pays'),
            ('recipient', 'Recipient Pays'),
            ('third_party', 'Third Party Pays'),
        ],
        string='Default Payment Method',
        default='sender',
    )
    ua_cod_enabled = fields.Boolean(
        string='COD Enabled',
        help='Cash on Delivery enabled',
    )
