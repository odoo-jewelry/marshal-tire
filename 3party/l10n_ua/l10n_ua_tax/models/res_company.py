from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Legal form
    l10n_ua_legal_form_id = fields.Many2one(
        'l10n_ua.legal.form',
        string='Legal Form',
        help='Організаційно-правова форма (ФОП, ТОВ, ПП, тощо)',
    )
    l10n_ua_is_fop = fields.Boolean(
        string='Is FOP',
        compute='_compute_is_fop',
        store=True,
    )

    # Tax office
    l10n_ua_tax_office_id = fields.Many2one(
        'l10n_ua.tax.office',
        string='Tax Office',
        help='Tax office (ДПІ) where the company is registered',
    )

    # FOP-specific settings (visible only when legal form is FOP)
    l10n_ua_fop_group = fields.Selection(
        selection=[
            ('1', 'Group 1'),
            ('2', 'Group 2'),
            ('3', 'Group 3'),
        ],
        string='FOP Group',
        default='3',
        help='Single tax payer group (1, 2, or 3)',
    )
    l10n_ua_tax_rate = fields.Float(
        string='Single Tax Rate (%)',
        default=5.0,
        help='Single tax rate percentage',
    )

    @api.depends('l10n_ua_legal_form_id', 'l10n_ua_legal_form_id.is_fop')
    def _compute_is_fop(self):
        for company in self:
            company.l10n_ua_is_fop = (
                company.l10n_ua_legal_form_id and
                company.l10n_ua_legal_form_id.is_fop
            )
