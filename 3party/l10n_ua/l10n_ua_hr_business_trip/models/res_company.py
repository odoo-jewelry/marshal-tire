from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ua_business_trip_daily_rate = fields.Monetary(
        string='Добові за день (норма)',
        currency_field='currency_id',
        help='Норма добових витрат на один день відрядження (за замовчуванням '
             'для нових звітів про відрядження). Неоподатковувана межа для '
             'відряджень у межах України — 0,1 мінімальної зарплати на день.',
    )
