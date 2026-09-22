from odoo import models, fields


class L10nUaBankPaymentLine(models.Model):
    _name = 'l10n_ua.bank.payment.line'
    _description = 'Bank Payment Line'

    payment_id = fields.Many2one(
        'l10n_ua.bank.payment', string='Payment', required=True,
        ondelete='cascade')
    recipient_name = fields.Char(string='Recipient', required=True)
    recipient_edrpou = fields.Char(string='EDRPOU/RNOKPP')
    recipient_iban = fields.Char(string='Recipient IBAN', required=True)
    amount = fields.Monetary(
        string='Amount', required=True, currency_field='currency_id')
    purpose = fields.Char(string='Payment Purpose')
    currency_id = fields.Many2one(
        'res.currency', related='payment_id.currency_id')
