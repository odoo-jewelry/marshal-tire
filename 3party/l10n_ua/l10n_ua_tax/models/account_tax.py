from odoo import fields, models


class AccountTax(models.Model):
    _inherit = 'account.tax'

    ua_tax_type = fields.Selection(
        selection=[
            ('pdfo', 'PDFO (Personal Income Tax)'),
            ('vz', 'VZ (Military Tax)'),
            ('esv', 'ESV (Unified Social Contribution)'),
            ('pdv', 'PDV (VAT)'),
            ('ep', 'EP (Single Tax)'),
            ('profit', 'Profit Tax'),
            ('other', 'Other'),
        ],
        string='UA Tax Type',
    )
    ua_tax_code = fields.Char(
        string='Tax Code',
        help='Tax code for reporting',
    )
    ua_budget_code_id = fields.Many2one(
        'l10n_ua.budget.code',
        string='Budget Code',
        help='Budget classification code for payment',
    )
