from odoo import fields, models


class L10nUaCompanyKved(models.Model):
    """Company KVED (activity codes) relation."""
    _name = 'l10n_ua.company.kved'
    _description = 'Company Activity Code (KVED)'
    _order = 'is_primary desc, sequence, id'

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        ondelete='cascade',
        index=True,
    )
    kved_id = fields.Many2one(
        'l10n_ua.kved',
        string='KVED',
        required=True,
        domain=[('level', '=', 4)],  # Only class-level codes (e.g., 62.01)
        ondelete='restrict',
    )
    code = fields.Char(
        string='Code',
        related='kved_id.code',
        store=True,
    )
    name = fields.Char(
        string='Name',
        related='kved_id.name',
        store=True,
    )
    is_primary = fields.Boolean(
        string='Primary',
        default=False,
        help='Mark as primary activity code',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )

    _unique_company_kved = models.Constraint(
        'UNIQUE(company_id, kved_id)',
        'This KVED code is already added to the company!',
    )
