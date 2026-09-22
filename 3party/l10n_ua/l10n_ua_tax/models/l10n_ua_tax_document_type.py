from odoo import fields, models


class L10nUaTaxDocumentType(models.Model):
    _name = 'l10n_ua.tax.document.type'
    _description = 'Tax Document Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )
    category = fields.Selection(
        selection=[
            ('declaration', 'Declaration'),
            ('report', 'Report'),
            ('receipt', 'Receipt'),
            ('notification', 'Notification'),
            ('request', 'Request'),
            ('response', 'Response'),
            ('other', 'Other'),
        ],
        string='Category',
        default='other',
    )
    active = fields.Boolean(
        default=True,
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'Document type code must be unique!',
    )
