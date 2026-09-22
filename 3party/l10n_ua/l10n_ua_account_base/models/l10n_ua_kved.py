from odoo import api, fields, models


class L10nUaKved(models.Model):
    _name = 'l10n_ua.kved'
    _description = 'KVED-2010 Classifier'
    _parent_name = 'parent_id'
    _parent_store = True
    _rec_name = 'complete_name'
    _order = 'code'

    code = fields.Char(
        string='Code',
        required=True,
        index=True,
        help='KVED code (e.g., 62.01)',
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
    section = fields.Char(
        string='Section',
        size=1,
        help='Section letter (A-U)',
    )
    parent_id = fields.Many2one(
        'l10n_ua.kved',
        string='Parent',
        index=True,
        ondelete='cascade',
    )
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many(
        'l10n_ua.kved',
        'parent_id',
        string='Children',
    )
    active = fields.Boolean(
        default=True,
    )
    level = fields.Integer(
        string='Level',
        compute='_compute_level',
        store=True,
        help='Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)',
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'KVED code must be unique!',
    )

    @api.depends('code', 'name')
    def _compute_complete_name(self):
        for record in self:
            record.complete_name = f'{record.code} {record.name}'

    @api.depends('code')
    def _compute_level(self):
        for record in self:
            code = record.code or ''
            if len(code) == 1:  # Section (A, B, C...)
                record.level = 1
            elif '.' not in code:  # Division (01, 02...)
                record.level = 2
            elif len(code.split('.')[1]) == 1:  # Group (01.1, 01.2...)
                record.level = 3
            else:  # Class (01.11, 01.12...)
                record.level = 4

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            domain = ['|', ('code', operator, name), ('name', operator, name)] + domain
        return self._search(domain, limit=limit, order=order)
