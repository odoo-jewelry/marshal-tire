from odoo import api, fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    ua_class = fields.Selection(
        selection=[
            ('0', '0 - Off-balance accounts'),
            ('1', '1 - Non-current assets'),
            ('2', '2 - Inventories'),
            ('3', '3 - Cash and settlements'),
            ('4', '4 - Equity and provisions'),
            ('5', '5 - Long-term liabilities'),
            ('6', '6 - Current liabilities'),
            ('7', '7 - Income'),
            ('8', '8 - Expenses by elements'),
            ('9', '9 - Activity expenses'),
        ],
        string='UA Account Class',
        compute='_compute_ua_class',
        store=True,
    )
    ua_subaccount = fields.Char(
        string='Subaccount',
        help='Subaccount code for analytical accounting',
    )
    ua_analytics_type = fields.Selection(
        selection=[
            ('none', 'No analytics'),
            ('partner', 'By partner'),
            ('product', 'By product'),
            ('department', 'By department'),
            ('employee', 'By employee'),
            ('contract', 'By contract'),
            ('custom', 'Custom'),
        ],
        string='Analytics Type',
        default='none',
    )
    ua_is_currency = fields.Boolean(
        string='Currency Account',
        help='Account with currency analytics',
    )
    ua_is_quantity = fields.Boolean(
        string='Quantity Account',
        help='Account with quantity analytics',
    )

    @api.depends('code')
    def _compute_ua_class(self):
        for account in self:
            if account.code and len(account.code) >= 1:
                first_digit = account.code[0]
                if first_digit.isdigit():
                    account.ua_class = first_digit
                else:
                    account.ua_class = False
            else:
                account.ua_class = False
