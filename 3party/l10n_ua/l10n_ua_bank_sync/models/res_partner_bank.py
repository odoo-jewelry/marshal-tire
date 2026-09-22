from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from odoo.addons.l10n_ua_account_base.tools.validators import validate_iban_ua


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    @api.constrains('acc_number')
    def _check_iban_ua(self):
        for account in self:
            if account.acc_number and account.acc_number.upper().startswith('UA'):
                is_valid, error = validate_iban_ua(account.acc_number)
                if not is_valid:
                    raise ValidationError(_('Invalid Ukrainian IBAN: %s') % error)

    @api.onchange('acc_number')
    def _onchange_acc_number_ua(self):
        if self.acc_number and self.acc_number.upper().startswith('UA') and len(self.acc_number) >= 10:
            mfo = self.acc_number[4:10]
            bank = self.env['res.bank'].search([('ua_mfo', '=', mfo)], limit=1)
            if bank:
                self.bank_id = bank
