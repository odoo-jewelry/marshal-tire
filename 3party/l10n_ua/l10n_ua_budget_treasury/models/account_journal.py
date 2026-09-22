from odoo import api, fields, models


TREASURY_ACCOUNT_TYPE = [
    ('registration', 'Реєстраційний'),
    ('special', 'Спеціальний реєстраційний'),
    ('depositary', 'Депозитний'),
    ('current', 'Поточний (валютний)'),
]


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    ua_is_treasury = fields.Boolean(
        string='Казначейський рахунок',
        help='Журнал прив\'язаний до рахунку в Державній казначейській службі (ДКСУ). '
             'Платежі по таких журналах вимагають перевірки ліміту асигнувань.')
    ua_treasury_organ_id = fields.Many2one(
        'l10n_ua.treasury.organ', string='Орган ДКСУ',
        help='Територіальний орган Казначейства, в якому відкрито рахунок')
    ua_treasury_account_type = fields.Selection(
        TREASURY_ACCOUNT_TYPE, string='Тип казначейського рахунку',
        help='Реєстраційний — для загального фонду; '
             'спеціальний — для власних надходжень; '
             'депозитний — для коштів, що утримуються тимчасово.')
    ua_treasury_kpkvk_id = fields.Many2one(
        'l10n_ua.kpkvk', string='КПКВК',
        help='Програма, до якої прив\'язаний реєстраційний рахунок')
    ua_treasury_fund_type = fields.Selection([
        ('general', 'Загальний фонд'),
        ('special', 'Спеціальний фонд'),
    ], string='Фонд',
       help='Фонд, який обслуговується цим рахунком. Платежі автоматично '
            'отримуватимуть це значення фонду.')
    ua_treasury_check_limit = fields.Boolean(
        string='Перевіряти ліміт асигнувань',
        default=True,
        help='Перед проведенням платежу перевіряти, що у відповідному рядку '
             'затвердженого кошторису є достатній залишок (план мінус факт).')

    @api.onchange('ua_is_treasury')
    def _onchange_ua_is_treasury(self):
        if not self.ua_is_treasury:
            self.ua_treasury_organ_id = False
            self.ua_treasury_account_type = False
            self.ua_treasury_kpkvk_id = False
            self.ua_treasury_fund_type = False
            self.ua_treasury_check_limit = False
        else:
            # sensible defaults
            if not self.ua_treasury_account_type:
                self.ua_treasury_account_type = 'registration'
            if not self.ua_treasury_fund_type:
                self.ua_treasury_fund_type = 'general'
