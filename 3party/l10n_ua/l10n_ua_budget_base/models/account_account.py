from odoo import fields, models


class AccountAccount(models.Model):
    _inherit = 'account.account'

    ua_budget_is_state_sector = fields.Boolean(
        string='Рахунок держсектору',
        help='Рахунок відноситься до плану рахунків бухобліку в державному секторі '
             '(Наказ Мінфіну № 1203). Не плутати з НП(С)БО приватного сектору.')
    ua_default_kekv_id = fields.Many2one(
        'l10n_ua.kekv',
        string='КЕКВ за замовчуванням',
        help='Економічна класифікація, що використовується за замовчуванням для проводок '
             'по цьому рахунку.')
    ua_default_kfk_id = fields.Many2one(
        'l10n_ua.kfk',
        string='КФК за замовчуванням',
        help='Функціональна класифікація для проводок по цьому рахунку.')
    ua_fund_type = fields.Selection([
        ('general', 'Загальний фонд'),
        ('special', 'Спеціальний фонд'),
        ('any', 'Будь-який'),
    ], string='Фонд', default='any',
       help='Якщо встановлено «загальний» або «спеціальний» — проводки по рахунку '
            'обмежуються відповідним фондом.')
