from odoo import fields, models


EDUCATION_INSTITUTION_TYPE = [
    ('zdo', 'Заклад дошкільної освіти (ЗДО)'),
    ('zzso', 'Заклад загальної середньої освіти (ЗЗСО)'),
    ('lyceum', 'Ліцей / гімназія'),
    ('pto', 'Професійно-технічний / професійний коледж (ПТУ/ВПУ)'),
    ('zvo_1_2', 'Заклад вищої освіти I-II рівнів акредитації (коледж/технікум)'),
    ('zvo_3_4', 'Заклад вищої освіти III-IV рівнів акредитації (університет/інститут)'),
    ('extracurricular', 'Позашкільний заклад'),
    ('other', 'Інше'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ua_education_type = fields.Selection(
        EDUCATION_INSTITUTION_TYPE, string='Тип закладу освіти',
        help='Тип освітнього закладу. Впливає на доступні види груп, рівні підготовки '
             'і набір документів. Не заповнюйте для не-освітніх установ.')
    l10n_ua_education_is_state = fields.Boolean(
        string='Державний / комунальний',
        help='Державна або комунальна форма власності — впливає на казначейське обслуговування.')
    l10n_ua_education_license_number = fields.Char(string='Номер ліцензії на освітню діяльність')
    l10n_ua_education_license_date = fields.Date(string='Дата видачі ліцензії')
    l10n_ua_education_iea_code = fields.Char(
        string='Код ЄДЕБО',
        help='Унікальний ідентифікатор закладу в Єдиній державній електронній базі освіти')
