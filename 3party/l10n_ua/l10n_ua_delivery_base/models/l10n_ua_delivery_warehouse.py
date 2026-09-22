from odoo import api, fields, models


class L10nUaDeliveryWarehouse(models.Model):
    _name = 'l10n_ua.delivery.warehouse'
    _description = 'Delivery Warehouse/Branch'
    _order = 'carrier_type, city, name'

    name = fields.Char(
        string='Name',
        required=True,
    )
    carrier_type = fields.Selection(
        selection=[
            ('novaposhta', 'Nova Poshta'),
            ('meest', 'Meest'),
            ('ukrposhta', 'Ukrposhta'),
        ],
        string='Carrier',
        required=True,
        index=True,
    )
    warehouse_ref = fields.Char(
        string='Warehouse Reference',
        index=True,
        help='External reference ID in carrier system',
    )
    warehouse_number = fields.Char(
        string='Warehouse Number',
    )
    warehouse_type = fields.Selection(
        selection=[
            ('warehouse', 'Warehouse'),
            ('postomat', 'Postomat'),
            ('cargo', 'Cargo Warehouse'),
        ],
        string='Type',
        default='warehouse',
    )
    city = fields.Char(
        string='City',
        index=True,
    )
    city_ref = fields.Char(
        string='City Reference',
    )
    address = fields.Char(
        string='Address',
    )
    phone = fields.Char(
        string='Phone',
    )
    schedule = fields.Text(
        string='Schedule',
    )
    max_weight = fields.Float(
        string='Max Weight (kg)',
    )
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 6),
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 6),
    )
    active = fields.Boolean(
        default=True,
    )

    _unique_ref_carrier = models.Constraint(
        'UNIQUE(warehouse_ref, carrier_type)',
        'Warehouse reference must be unique per carrier!',
    )

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []
        if name:
            args = ['|', '|',
                    ('name', operator, name),
                    ('warehouse_number', operator, name),
                    ('city', operator, name)] + args
        return self._search(args, limit=limit)
