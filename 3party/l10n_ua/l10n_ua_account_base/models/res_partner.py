from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..tools.validators import validate_edrpou, validate_ipn


class ResPartner(models.Model):
    _inherit = 'res.partner'

    edrpou = fields.Char(
        string='EDRPOU',
        size=8,
        help='Unified State Register of Enterprises and Organizations of Ukraine (8 digits)',
    )
    ipn = fields.Char(
        string='IPN/RNOKPP',
        size=12,
        help='Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)',
    )
    legal_form = fields.Selection(
        selection=[
            ('fop', 'FOP (Individual Entrepreneur)'),
            ('tov', 'TOV (LLC)'),
            ('pp', 'PP (Private Enterprise)'),
            ('pat', 'PAT (Public Joint Stock Company)'),
            ('prat', 'PrAT (Private Joint Stock Company)'),
            ('kp', 'KP (Communal Enterprise)'),
            ('dp', 'DP (State Enterprise)'),
            ('go', 'GO (Public Organization)'),
            ('bf', 'BF (Charitable Foundation)'),
            ('other', 'Other'),
        ],
        string='Legal Form',
    )
    is_vat_payer = fields.Boolean(
        string='VAT Payer',
        default=False,
    )
    vat_certificate = fields.Char(
        string='VAT Certificate Number',
    )
    primary_kved_id = fields.Many2one(
        'l10n_ua.kved',
        string='Primary KVED',
        help='Primary economic activity code',
    )
    kved_ids = fields.Many2many(
        'l10n_ua.kved',
        'res_partner_kved_rel',
        'partner_id',
        'kved_id',
        string='KVED Codes',
        help='All economic activity codes',
    )
    l10n_ua_chief_name = fields.Char(
        string='Chief Name',
        help='ПІБ керівника (director / responsible person)',
    )
    l10n_ua_chief_position = fields.Char(
        string='Chief Position',
        default='Директор',
        help='Посада керівника',
    )
    l10n_ua_accountant_name = fields.Char(
        string='Chief Accountant',
        help='ПІБ головного бухгалтера',
    )
    l10n_ua_legal_address = fields.Char(
        string='Legal Address',
        help='Юридична адреса (якщо відрізняється від фактичної)',
    )

    @api.constrains('edrpou')
    def _check_edrpou(self):
        for partner in self:
            if partner.edrpou:
                is_valid, error = validate_edrpou(partner.edrpou)
                if not is_valid:
                    raise ValidationError(_('Invalid EDRPOU: %s') % error)

    @api.constrains('ipn')
    def _check_ipn(self):
        for partner in self:
            if partner.ipn:
                is_valid, error = validate_ipn(partner.ipn)
                if not is_valid:
                    raise ValidationError(_('Invalid IPN/RNOKPP: %s') % error)
