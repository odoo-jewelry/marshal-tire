from odoo import api, fields, models


class L10nUaPrroConfig(models.Model):
    _name = 'l10n_ua.prro.config'
    _description = 'PRRO Configuration'
    _inherit = ['l10n_ua.prro.mixin']

    name = fields.Char(
        string='Name',
        required=True,
    )
    fiscal_number = fields.Char(
        string='Fiscal Number',
        help='PRRO fiscal number',
    )
    provider = fields.Selection(
        selection=[
            ('checkbox', 'Checkbox'),
            ('vchasno', 'Vchasno Kasa'),
            ('other', 'Other'),
        ],
        string='Provider',
        required=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    pos_config_ids = fields.Many2many(
        'pos.config',
        string='POS Configurations',
    )
    state = fields.Selection(
        selection=[
            ('not_configured', 'Not Configured'),
            ('configured', 'Configured'),
            ('active', 'Active'),
            ('error', 'Error'),
        ],
        string='State',
        default='not_configured',
    )
    current_shift_id = fields.Many2one(
        'l10n_ua.prro.shift',
        string='Current Shift',
        compute='_compute_current_shift',
    )
    error_message = fields.Text(
        string='Error Message',
    )

    def _compute_current_shift(self):
        for config in self:
            shift = self.env['l10n_ua.prro.shift'].search([
                ('config_id', '=', config.id),
                ('state', '=', 'open'),
            ], limit=1)
            config.current_shift_id = shift

    prro_provider = fields.Selection(
        selection_add=[
            ('checkbox', 'Checkbox'),
            ('vchasno', 'Vchasno Kasa'),
        ],
        ondelete={'checkbox': 'set default', 'vchasno': 'set default'},
    )
