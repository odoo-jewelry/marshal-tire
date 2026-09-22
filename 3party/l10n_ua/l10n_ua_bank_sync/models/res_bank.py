from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import re


class ResBank(models.Model):
    _inherit = 'res.bank'

    ua_mfo = fields.Char(
        string='MFO Code',
        size=6,
        help='Ukrainian bank MFO code (6 digits)',
    )

    @api.constrains('ua_mfo')
    def _check_mfo(self):
        for bank in self:
            if bank.ua_mfo:
                if not re.match(r'^\d{6}$', bank.ua_mfo):
                    raise ValidationError(_('MFO code must be exactly 6 digits'))
