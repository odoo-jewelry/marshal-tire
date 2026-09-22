from odoo import api, fields, models


class L10nUaTaxOffice(models.Model):
    """Ukrainian Tax Office (ДПІ) directory."""
    _name = 'l10n_ua.tax.office'
    _description = 'Tax Office (ДПІ)'
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(
        string='Code (C_STI)',
        required=True,
        index=True,
        help='Full tax office code (4 digits), e.g., 2658',
    )
    c_reg = fields.Char(
        string='Region Code (C_REG)',
        size=2,
        compute='_compute_codes',
        store=True,
        help='Region code (first 2 digits of C_STI)',
    )
    c_raj = fields.Char(
        string='District Code (C_RAJ)',
        size=2,
        compute='_compute_codes',
        store=True,
        help='District code (last 2 digits of C_STI)',
    )
    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    short_name = fields.Char(
        string='Short Name',
        translate=True,
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True,
    )
    region_id = fields.Many2one(
        'res.country.state',
        string='Region',
        domain=[('country_id.code', '=', 'UA')],
        help='Ukrainian region (oblast)',
    )
    parent_id = fields.Many2one(
        'l10n_ua.tax.office',
        string='Parent Office',
        help='Parent tax office (for district offices)',
        ondelete='cascade',
    )
    child_ids = fields.One2many(
        'l10n_ua.tax.office',
        'parent_id',
        string='Child Offices',
    )
    office_type = fields.Selection(
        selection=[
            ('central', 'Central Office (ДПС)'),
            ('regional', 'Regional Office (ГУ ДПС)'),
            ('district', 'District Office (ДПІ)'),
        ],
        string='Office Type',
        default='district',
    )
    address = fields.Text(
        string='Address',
    )
    phone = fields.Char(
        string='Phone',
    )
    email = fields.Char(
        string='Email',
    )
    active = fields.Boolean(
        default=True,
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'Tax office code must be unique!',
    )

    @api.depends('code')
    def _compute_codes(self):
        for record in self:
            code = record.code or ''
            record.c_reg = code[:2] if len(code) >= 2 else ''
            record.c_raj = code[2:4] if len(code) >= 4 else ''

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f'{record.code} - {record.name}' if record.code else record.name

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            domain = [
                '|', '|',
                ('code', operator, name),
                ('name', operator, name),
                ('short_name', operator, name),
            ] + domain
        return self._search(domain, limit=limit, order=order)
