from odoo import api, fields, models


class L10nUaAddressMixin(models.AbstractModel):
    _name = 'l10n_ua.address.mixin'
    _description = 'Ukrainian Address Mixin'

    koatuu_id = fields.Many2one(
        'l10n_ua.koatuu',
        string='KOATUU',
        help='Settlement from KOATUU/KATOTTG directory',
    )
    ua_region = fields.Char(
        string='Region (Oblast)',
    )
    ua_district = fields.Char(
        string='District (Raion)',
    )
    ua_community = fields.Char(
        string='Community (Hromada)',
    )
    ua_city = fields.Char(
        string='City/Village',
    )
    ua_street = fields.Char(
        string='Street',
    )
    ua_building = fields.Char(
        string='Building',
    )
    ua_apartment = fields.Char(
        string='Apartment',
    )
    ua_postal_code = fields.Char(
        string='Postal Code',
        size=5,
    )
    ua_full_address = fields.Char(
        string='Full Address',
        compute='_compute_ua_full_address',
        store=True,
    )

    @api.depends('ua_postal_code', 'ua_region', 'ua_district', 'ua_city', 'ua_street', 'ua_building', 'ua_apartment')
    def _compute_ua_full_address(self):
        for record in self:
            parts = []
            if record.ua_postal_code:
                parts.append(record.ua_postal_code)
            if record.ua_region:
                parts.append(record.ua_region)
            if record.ua_district:
                parts.append(record.ua_district)
            if record.ua_city:
                parts.append(record.ua_city)
            if record.ua_street:
                parts.append(f'вул. {record.ua_street}')
            if record.ua_building:
                parts.append(f'буд. {record.ua_building}')
            if record.ua_apartment:
                parts.append(f'кв. {record.ua_apartment}')
            record.ua_full_address = ', '.join(parts) if parts else False

    @api.onchange('koatuu_id')
    def _onchange_koatuu_id(self):
        if self.koatuu_id:
            self.ua_city = self.koatuu_id.name
            parent = self.koatuu_id.parent_id
            while parent:
                if parent.level == 'community':
                    self.ua_community = parent.name
                elif parent.level == 'district':
                    self.ua_district = parent.name
                elif parent.level == 'region':
                    self.ua_region = parent.name
                parent = parent.parent_id
