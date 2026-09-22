from odoo import fields, models


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'

    inverse_company_rate = fields.Float(
        string='Rate (UAH)',
        digits=(12, 6),
        help='Exchange rate: 1 foreign currency = X UAH',
    )
    provider_id = fields.Many2one(
        'res.currency.rate.provider',
        string='Provider',
        help='Source of this rate',
    )
