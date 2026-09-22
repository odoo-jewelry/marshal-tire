"""Ліміти груп ЄП і ЄСВ декларації — з довідника мінзарплати (#325).

Покриття:
- ліміти 2025 і 2026 років для всіх груп (167 / 834 / 1167 мінзарплат на 01.01);
- ЄСВ за півріччя 2026 — випадок із #325: 6 × 8647 × 22% = 11 414,04;
- ЄСВ за 2024 рік іде за підвищенням мінзарплати з 1 квітня;
- перевищення ліміту;
- рік без мінзарплати в довіднику — розрахунок відмовляє, а не рахує від нуля;
- запис, доданий у довідник пізніше, підхоплюється наявною декларацією.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFopMinWageLimits(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.groups = {
            code: cls.env.ref(f'l10n_ua_fop.fop_group_{code}')
            for code in ('1', '2', '3', '3_vat')
        }

    def _books(self, year, group, amounts_by_quarter):
        for quarter, amount in amounts_by_quarter.items():
            book = self.env['l10n_ua.fop.income.book'].create({
                'year': year,
                'quarter': quarter,
                'fop_group_id': group.id,
                'company_id': self.company.id,
            })
            self.env['l10n_ua.fop.income.book.line'].create({
                'book_id': book.id,
                'date': date(year, {'1': 1, '2': 4, '3': 7, '4': 10}[quarter], 15),
                'amount': amount,
                'description': f'Дохід Q{quarter}',
            })
            book.action_confirm()

    def _declaration(self, year, period, group):
        return self.env['l10n_ua.fop.declaration'].create({
            'year': year,
            'period': period,
            'fop_group_id': group.id,
            'company_id': self.company.id,
        })

    def test_group_income_limits(self):
        expected = {
            2025: {'1': 1_336_000, '2': 6_672_000, '3': 9_336_000, '3_vat': 9_336_000},
            2026: {'1': 1_444_049, '2': 7_211_598, '3': 10_091_049, '3_vat': 10_091_049},
        }
        for year, limits in expected.items():
            for code, limit in limits.items():
                with self.subTest(year=year, group=code):
                    self.assertEqual(self.groups[code]._get_income_limit(year), limit)
                    self.assertEqual(
                        self._declaration(year, 'q1', self.groups[code]).income_limit, limit)

    def test_esv_half_year_2026(self):
        group = self.groups['3']
        self._books(2026, group, {'1': 100_000, '2': 120_000})
        decl = self._declaration(2026, 'h1', group)
        decl.action_calculate()
        self.assertEqual(decl.min_wage, 8647)
        self.assertEqual(decl.esv_base, 51_882)          # 6 × 8647
        self.assertAlmostEqual(decl.esv_amount, 11_414.04, places=2)

    def test_esv_2024_follows_april_increase(self):
        group = self.groups['3']
        self._books(2024, group, {'1': 1000, '2': 1000, '3': 1000, '4': 1000})
        decl = self._declaration(2024, 'year', group)
        decl.action_calculate()
        self.assertEqual(decl.esv_base, 3 * 7100 + 9 * 8000)
        self.assertEqual(decl.min_wage, 8000)

    def test_income_over_limit_is_flagged(self):
        group = self.groups['1']
        self._books(2026, group, {'1': 1_444_050})
        decl = self._declaration(2026, 'q1', group)
        decl.action_calculate()
        self.assertTrue(decl.income_limit_exceeded)

    def test_income_at_limit_is_not_flagged(self):
        group = self.groups['1']
        self._books(2026, group, {'1': 1_444_049})
        decl = self._declaration(2026, 'q1', group)
        decl.action_calculate()
        self.assertFalse(decl.income_limit_exceeded)

    def test_calculate_refuses_year_without_min_wage(self):
        group = self.groups['3']
        self._books(2099, group, {'1': 50_000})
        decl = self._declaration(2099, 'q1', group)
        with self.assertRaises(UserError):
            decl.action_calculate()
        self.assertEqual(decl.state, 'draft')

    def test_min_wage_added_later_is_used(self):
        group = self.groups['3']
        self._books(2099, group, {'1': 50_000})
        decl = self._declaration(2099, 'q1', group)
        self.assertEqual(decl.min_wage, 0.0)

        self.env['l10n_ua.min.wage'].create({'date_from': date(2099, 1, 1), 'amount': 20_000})
        decl.action_calculate()
        self.assertEqual(decl.min_wage, 20_000)
        self.assertEqual(decl.esv_base, 60_000)
        self.assertEqual(decl.income_limit, 1167 * 20_000)
