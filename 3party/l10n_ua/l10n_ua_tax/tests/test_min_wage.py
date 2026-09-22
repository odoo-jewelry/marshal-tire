"""Довідник мінімальної заробітної плати (#325).

Покриття:
- офіційні розміри 2024–2026 заведено, зокрема підвищення з 01.04.2024;
- сума на дату береться лише з того самого року — рік без запису дає 0,
  а не мовчки розмір попереднього року;
- дата початку дії унікальна, сума додатна.
"""

from datetime import date

from psycopg2 import IntegrityError

from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestMinWage(TransactionCase):

    def setUp(self):
        super().setUp()
        self.MinWage = self.env['l10n_ua.min.wage']

    def test_official_amounts(self):
        cases = [
            (date(2024, 3, 31), 7100),
            (date(2024, 4, 1), 8000),
            (date(2025, 1, 1), 8000),
            (date(2025, 12, 31), 8000),
            (date(2026, 1, 1), 8647),
            (date(2026, 9, 1), 8647),
        ]
        for on_date, amount in cases:
            with self.subTest(on_date=on_date):
                self.assertEqual(self.MinWage._get_amount(on_date), amount)

    def test_year_without_record_is_not_filled_from_previous_year(self):
        self.assertEqual(self.MinWage._get_amount(date(2099, 6, 1)), 0.0)

    def test_new_year_record_is_picked_up(self):
        self.MinWage.create({'date_from': date(2099, 1, 1), 'amount': 20000})
        self.assertEqual(self.MinWage._get_amount(date(2099, 6, 1)), 20000)

    def test_date_from_is_unique(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.MinWage.create({'date_from': date(2026, 1, 1), 'amount': 9000})

    def test_amount_must_be_positive(self):
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            self.MinWage.create({'date_from': date(2098, 1, 1), 'amount': 0})

    def test_readable_without_tax_accountant_group(self):
        user = self.env['res.users'].create({
            'name': 'Бухгалтер ФОП', 'login': 'fop_min_wage_reader',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })
        self.assertEqual(self.MinWage.with_user(user)._get_amount(date(2026, 5, 1)), 8647)
