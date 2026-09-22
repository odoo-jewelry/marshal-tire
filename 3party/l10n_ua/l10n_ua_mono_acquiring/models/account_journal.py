from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    mono_acquiring_token = fields.Char(
        string="Токен Monobank Acquiring",
        help="Токен мерчанта з кабінету Monobank (розділ Acquiring). "
             "Прив'язується до банківського журналу, куди зараховуються "
             "карткові оплати.",
    )
