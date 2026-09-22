from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    edrpou = fields.Char(
        string='EDRPOU', size=8,
        help='Unified State Register of Enterprises and Organizations of Ukraine code')
    koatuu = fields.Char(
        string='KOATUU', size=10,
        help='Code of the Classification of Administrative-Territorial Units of Ukraine')
    katottg = fields.Char(
        string='KATOTTG', size=19,
        help='Код КАТОТТГ (кодифікатор адміністративно-територіальних одиниць), '
             'формат UA + 17 цифр. Потрібен для звітності 4ДФ/об\'єднаного розрахунку.')
    legal_address = fields.Text(string='Legal Address')
    tax_office_code = fields.Char(
        string='Tax Office Code',
        help='Code of the tax office (DPI)')
    pension_fund_code = fields.Char(
        string='Pension Fund Code',
        help='Code of the pension fund office (PFU)')
    kved_main = fields.Char(
        string='Main KVED',
        help='Main economic activity code (KVED)')
    ownership_form = fields.Selection([
        ('private', 'Private'),
        ('state', 'State'),
        ('communal', 'Communal'),
        ('collective', 'Collective'),
        ('mixed', 'Mixed'),
    ], string='Ownership Form')
