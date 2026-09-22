from odoo import fields, models


MEDECIN_INSTITUTION_TYPE = [
    ('cmsd', 'Центр первинної медико-санітарної допомоги (ЦПМСД)'),
    ('asmd', 'Амбулаторія сімейної медицини (АСМД)'),
    ('clinic', 'Поліклініка'),
    ('hospital', 'Лікарня'),
    ('mch', 'Пологовий будинок'),
    ('emergency', 'Станція/центр екстреної медичної допомоги (ЕМД)'),
    ('diagnostic', 'Діагностичний центр'),
    ('rehab', 'Реабілітаційний центр'),
    ('sanatorium', 'Санаторно-курортний заклад'),
    ('dispensary', 'Диспансер (туб., нарко., психо.)'),
    ('lab', 'Лабораторія'),
    ('pharma', 'Аптека (бюджетна)'),
    ('other', 'Інше'),
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ua_medecin_type = fields.Selection(
        MEDECIN_INSTITUTION_TYPE, string='Тип закладу охорони здоров\'я',
        help='Тип медичного закладу. Впливає на доступні пакети НСЗУ та структуру звітності.')
    l10n_ua_medecin_is_state = fields.Boolean(
        string='Державний / комунальний',
        help='Державна або комунальна форма власності — впливає на казначейське обслуговування.')
    l10n_ua_medecin_license_number = fields.Char(string='Номер ліцензії МОЗ')
    l10n_ua_medecin_license_date = fields.Date(string='Дата видачі ліцензії')
    l10n_ua_medecin_nszu_id = fields.Char(
        string='ID надавача в НСЗУ',
        help='Унікальний ідентифікатор закладу як надавача медичних послуг у НСЗУ '
             '(використовується для електронних договорів).')
    l10n_ua_medecin_ehealth_id = fields.Char(
        string='ID в eHealth',
        help='Ідентифікатор закладу в Центральній компоненті eHealth.')
    l10n_ua_medecin_specialty_ids = fields.Many2many(
        'l10n_ua.medecin.specialty', string='Спеціалізації / профілі',
        help='Перелік медичних спеціалізацій, за якими заклад надає послуги.')
