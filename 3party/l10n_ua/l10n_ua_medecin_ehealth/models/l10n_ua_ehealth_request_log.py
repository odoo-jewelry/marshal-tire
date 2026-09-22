from odoo import fields, models


class L10nUaEhealthRequestLog(models.Model):
    _name = 'l10n_ua.ehealth.request.log'
    _description = 'Лог запитів до eHealth'
    _order = 'create_date desc'
    _rec_name = 'operation'

    operation = fields.Char(string='Операція', required=True, index=True)
    method = fields.Char(string='HTTP метод', required=True)
    url = fields.Char(string='URL', required=True)
    request_body = fields.Text(string='Тіло запиту')
    response_status = fields.Integer(string='HTTP-статус')
    response_body = fields.Text(string='Тіло відповіді')
    reference = fields.Char(string='Посилання', index=True,
                              help='Зовнішній ідентифікатор для пошуку (наприклад, номер декларації).')
