from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Activity codes for tax cabinet documents
    l10n_ua_kved_ids = fields.One2many(
        'l10n_ua.company.kved',
        'company_id',
        string='Activity Codes (KVED)',
    )
