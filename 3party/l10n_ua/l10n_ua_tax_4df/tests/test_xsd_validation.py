"""Валідація згенерованого XML Додатка 4ДФ проти офіційного XSD ДПС.

XSD `tests/schemas/F0510410.xsd` (+ `J0510410.xsd`, `common_types.xsd`) —
контрольні схеми з пакета СКЗ ДПС (повна версія 1.34.0.0,
tax.gov.ua/data/files/627351.zip). Публічні держсхеми, вендоряться як
тест-фікстури. Оновлювати при зміні версії форми (docs/forms-watch-playbook.md).
"""

import os
from datetime import date

from lxml import etree

from odoo.tests import TransactionCase, tagged

SCHEMA_DIR = os.path.join(os.path.dirname(__file__), 'schemas')


@tagged('post_install', '-at_install')
class TestD4XsdValidation(TransactionCase):

    def _sample_vals(self, prefix='F05'):
        # 10-значні коди РНОКПП/ЄДРПОУ — валідні для DGHTINF (9/10 цифр).
        # Реальний 8-значний ЄДРПОУ юрособи — окремий нюанс мапінгу HTIN.
        return {
            'prefix': prefix,
            'tin': '2940910418',
            'doc_type': 0, 'doc_cnt': 1,
            'c_reg': '17', 'c_raj': '16',
            'period_month': 3, 'period_type': 2, 'period_year': 2026,
            'c_sti_orig': '1716', 'doc_stan': 1, 'd_fill': '15072026',
            'hzy': 2026, 'hzm': 3, 'hnum': 1,
            'hname': 'ТОВ Тест', 'htin': '2940910418',
            'hkatottg': 'UA' + '0' * 17,
            'hkbos': '2940910418', 'hbos': 'Директор Тест',
            'persons': [
                {'rnokpp': '1234567890', 'income_accrued': 10000.0,
                 'income_paid': 10000.0, 'pdfo_accrued': 1800.0,
                 'pdfo_paid': 1800.0, 'mil_accrued': 500.0, 'mil_paid': 500.0,
                 'income_code': '101', 'date_hire': date(2026, 1, 10),
                 'date_term': None, 'ozn': '0'},
                {'rnokpp': '0987654321', 'income_accrued': 15000.0,
                 'income_paid': 15000.0, 'pdfo_accrued': 2700.0,
                 'pdfo_paid': 2700.0, 'mil_accrued': 750.0, 'mil_paid': 750.0,
                 'income_code': '101', 'date_hire': None,
                 'date_term': date(2026, 3, 20), 'ozn': '0'},
            ],
        }

    def _schema(self, prefix):
        fname = ('F' if prefix == 'F05' else 'J') + '0510410.xsd'
        return etree.XMLSchema(etree.parse(os.path.join(SCHEMA_DIR, fname)))

    def test_d4_validates_against_official_xsd(self):
        model = self.env['l10n_ua.tax.4df']
        for prefix in ('F05', 'J05'):
            xml = model._render_d4_xml(self._sample_vals(prefix))
            doc = etree.fromstring(xml.encode('windows-1251'))
            schema = self._schema(prefix)
            schema.assertValid(doc)  # деталі — у DocumentInvalid

    def test_d4_empty_person_list_validates(self):
        """Звіт без осіб теж має давати валідний за схемою документ."""
        model = self.env['l10n_ua.tax.4df']
        vals = self._sample_vals('F05')
        vals['persons'] = []
        xml = model._render_d4_xml(vals)
        doc = etree.fromstring(xml.encode('windows-1251'))
        self.assertTrue(self._schema('F05').validate(doc),
                        self._schema('F05').error_log)
