from odoo import fields, models


class L10nUaBudgetCode(models.Model):
    _name = 'l10n_ua.budget.code'
    _description = 'Budget Classification Code'
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
    tax_type = fields.Selection(
        selection=[
            ('pdfo', 'PDFO'),
            ('vz', 'Military Tax'),
            ('esv', 'ESV'),
            ('pdv', 'VAT'),
            ('ep', 'Single Tax'),
            ('profit', 'Profit Tax'),
            ('other', 'Other'),
        ],
        string='Tax Type',
    )
    active = fields.Boolean(
        default=True,
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'Budget code must be unique!',
    )
