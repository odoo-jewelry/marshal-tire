"""Реквізити компанії доступні без кадрового блоку (#292)."""
from odoo.tests import TransactionCase, tagged

REGISTRATION_FIELDS = [
    'edrpou', 'koatuu', 'katottg', 'legal_address',
    'tax_office_code', 'pension_fund_code', 'kved_main', 'ownership_form',
]

# Те, що лишилось кадровим і сюди приходити не має: підписанти — це
# `hr.employee`, а модуль залежить лише від `base`.
HR_FIELDS = ['director_id', 'accountant_id', 'hr_manager_id',
             'military_officer_id', 'wage_from_staffing']


@tagged('post_install', '-at_install', 'l10n_ua_company_base')
class TestCompanyRegistrationFields(TransactionCase):

    def test_fields_exist_on_company(self):
        fields = self.env['res.company']._fields
        for name in REGISTRATION_FIELDS:
            with self.subTest(field=name):
                self.assertIn(name, fields)

    def test_fields_belong_to_this_module(self):
        """Власник поля має бути саме цей модуль.

        Доти реквізити оголошував `l10n_ua_hr_base`, і податковий кабінет не
        міг їх прочитати, не втягнувши кадри. Якщо оголошення колись поповзе
        назад, тест це помітить.
        """
        declared = self.env['ir.model.fields'].search([
            ('model', '=', 'res.company'),
            ('name', 'in', REGISTRATION_FIELDS),
        ])
        self.assertEqual(len(declared), len(REGISTRATION_FIELDS))
        for field in declared:
            with self.subTest(field=field.name):
                self.assertIn('l10n_ua_company_base', field.modules)

    def test_registration_data_round_trips(self):
        company = self.env['res.company'].create({'name': 'ТОВ Реквізити'})
        company.write({
            'edrpou': '12345678',
            'katottg': 'UA05020030010063857',
            'tax_office_code': '1716',
            'pension_fund_code': '1234',
            'ownership_form': 'private',
        })
        self.assertEqual(company.edrpou, '12345678')
        self.assertEqual(company.katottg, 'UA05020030010063857')
        self.assertEqual(company.tax_office_code, '1716')
        self.assertEqual(company.ownership_form, 'private')

    def test_hr_fields_are_not_dragged_in(self):
        """Модуль залежить лише від `base` — кадрових полів тут бути не може.

        На базі з установленим `l10n_ua_hr_base` вони, звісно, є; тест має сенс
        саме на чистій установці самого цього модуля, тому перевіряємо не
        відсутність, а походження: якщо поле є, то не від нас.
        """
        declared = self.env['ir.model.fields'].search([
            ('model', '=', 'res.company'),
            ('name', 'in', HR_FIELDS),
        ])
        for field in declared:
            with self.subTest(field=field.name):
                self.assertNotIn('l10n_ua_company_base', field.modules)
