from odoo import api, fields, models


class L10nUaKoatuu(models.Model):
    _name = 'l10n_ua.koatuu'
    _description = 'KOATUU/KATOTTG Directory'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'code'

    code = fields.Char(
        string='Code',
        required=True,
        index=True,
    )
    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    complete_name = fields.Char(
        string='Complete Name',
        compute='_compute_complete_name',
        recursive=True,
        store=True,
    )
    parent_id = fields.Many2one(
        'l10n_ua.koatuu',
        string='Parent',
        index=True,
        ondelete='cascade',
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'l10n_ua.koatuu',
        'parent_id',
        string='Children',
    )
    level = fields.Selection(
        selection=[
            ('region', 'Region (Oblast)'),
            ('district', 'District (Raion)'),
            ('community', 'Community (Hromada)'),
            ('city', 'City'),
            ('village', 'Village/Settlement'),
        ],
        string='Level',
    )
    category = fields.Selection(
        selection=[
            ('city', 'City'),
            ('town', 'Town'),
            ('village', 'Village'),
            ('settlement', 'Urban Settlement'),
        ],
        string='Category',
    )
    active = fields.Boolean(
        default=True,
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'KOATUU code must be unique!',
    )

    @api.depends('name', 'parent_id.complete_name')
    def _compute_complete_name(self):
        for record in self:
            if record.parent_id:
                record.complete_name = f'{record.parent_id.complete_name} / {record.name}'
            else:
                record.complete_name = record.name

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)
