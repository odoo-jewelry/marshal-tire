"""Валідація згенерованого XML Додатка 1 (ЄСВ) проти офіційного XSD ДПС (#187).

XSD `tests/schemas/J0510210.xsd` (+ common_types.xsd) — контрольні схеми з
пакета СКЗ ДПС (повна версія, tax.gov.ua/data/files/627351.zip). Публічні
держсхеми, вендоряться як тест-фікстури. Оновлювати при зміні версії форми
(див. docs/forms-watch-playbook.md).
"""

import os
from datetime import date

from lxml import etree

from odoo.tests import TransactionCase, tagged

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schemas', 'J0510210.xsd')


@tagged('post_install', '-at_install')
class TestD5XsdValidation(TransactionCase):

    def _sample_vals(self):
        return {
            'tin': '12345678',
            'c_reg': 17,
            'c_raj': 16,
            'period_month': 6,
            'period_type': 1,
            'period_year': 2025,
            'c_sti_orig': '1716',
            'hzy': 2025,
            'hzm': 6,
            'hname': 'ТОВ Тест',
            'htin': '12345678',
            'hfill': date.today().strftime('%d%m%Y'),
            'hkbos': '2940910418',
            'hbos': 'Петренко О.М.',
            'hkbuh': '3184710691',
            'hbuh': 'Іваненко Н.П.',
            'persons': [
                {'rnokpp': '3184710691', 'last_name': 'Петренко',
                 'first_name': 'Олександр', 'middle_name': 'Миколайович',
                 'zo_category': 1, 'esv_base': 25000.0, 'esv_amount': 5500.0},
                {'rnokpp': '2940910418', 'last_name': 'Коваль',
                 'first_name': 'Ірина', 'middle_name': '',
                 'zo_category': 26, 'esv_base': 10000.0, 'esv_amount': 2200.0},
            ],
        }

    def _schema(self):
        return etree.XMLSchema(etree.parse(SCHEMA_PATH))

    def _validate(self, vals):
        xml = self.env['hr.report.d5']._render_d1_xml(vals)
        # Подання йде у windows-1251 — валідуємо саме ті байти, що підуть у ДПС.
        doc = etree.fromstring(xml.encode('windows-1251'))
        schema = self._schema()
        self.assertTrue(
            schema.validate(doc),
            'XSD-невалідний XML: %s' % schema.error_log)

    def test_full_validates(self):
        self._validate(self._sample_vals())

    def test_empty_persons_validates(self):
        vals = self._sample_vals()
        vals['persons'] = []
        self._validate(vals)

    def test_without_accountant_validates(self):
        vals = self._sample_vals()
        vals['hkbuh'] = ''
        vals['hbuh'] = ''
        self._validate(vals)

    def test_fixed_head_codes(self):
        xml = self.env['hr.report.d5']._render_d1_xml(self._sample_vals())
        self.assertIn('<C_DOC>J05</C_DOC>', xml)
        self.assertIn('<C_DOC_SUB>102</C_DOC_SUB>', xml)
        self.assertIn('<C_DOC_VER>10</C_DOC_VER>', xml)
