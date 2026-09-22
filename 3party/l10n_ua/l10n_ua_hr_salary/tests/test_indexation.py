"""Тести індексації заробітної плати (#138).

Метод наростаючого підсумку (Порядок №1078): місячні індекси споживчих цін
перемножуються від місяця, наступного за базовим; при перевищенні порогу (101%)
приріст фіксується у % індексації, а наростання починається заново.
"""

from datetime import date

from .common import SalaryTestCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestIndexation(SalaryTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Cpi = cls.env['hr.cpi.index']
        # Реєстр ІСЦ: базовий місяць — 01.2025.
        for m, val in [
            (date(2025, 2, 1), 100.6),
            (date(2025, 3, 1), 100.5),
            (date(2025, 4, 1), 100.8),
            (date(2025, 5, 1), 100.7),
        ]:
            cls.Cpi.create({
                'month': m, 'index_value': val, 'company_id': cls.company.id})
        cls.version.write({
            'indexation_enabled': True,
            'indexation_base_month': date(2025, 1, 1),
        })

    def _percent(self, target):
        return self.Cpi.get_indexation_percent(
            date(2025, 1, 1), target, 101.0, self.company.id)

    # --- Алгоритм наростаючого підсумку ---

    def test_below_threshold_no_indexation(self):
        # 02.2025: наростаючий 100.6 < 101 → 0%.
        self.assertEqual(self._percent(date(2025, 2, 28)), 0.0)

    def test_threshold_crossed(self):
        # 03.2025: 100.6 × 100.5 = 101.1 > 101 → приріст 1.1%.
        self.assertAlmostEqual(self._percent(date(2025, 3, 31)), 1.1, places=1)

    def test_accumulates_after_reset(self):
        # Після скидання на 03: 04 → 100.8, 05 → 100.8×100.7=101.5 → +1.5.
        # Разом 1.1 + 1.5 = 2.6%.
        self.assertAlmostEqual(self._percent(date(2025, 5, 31)), 2.6, places=1)

    def test_before_base_month_is_zero(self):
        self.assertEqual(self._percent(date(2024, 12, 31)), 0.0)

    def test_missing_months_treated_as_no_growth(self):
        # Місяців без даних немає в реєстрі → трактуються як 100% (без приросту).
        pct = self.Cpi.get_indexation_percent(
            date(2025, 5, 1), date(2025, 8, 31), 101.0, self.company.id)
        self.assertEqual(pct, 0.0)

    # --- Генерація нарахування у розрахунковому листку ---

    def _payslip(self, date_to, worked=20, scheduled=20):
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date_to.replace(day=1),
            'date_to': date_to,
        })
        slip.write({
            'scheduled_days': scheduled, 'worked_days': worked,
            'scheduled_hours': 160.0, 'worked_hours': 160.0,
        })
        return slip

    def _indexation(self, slip):
        return slip.accrual_ids.filtered(
            lambda a: a.accrual_type_id.code == 'INDEXATION')

    def test_payslip_indexation_full_month(self):
        slip = self._payslip(date(2025, 3, 31))
        slip._generate_accruals()
        acc = self._indexation(slip)
        self.assertEqual(len(acc), 1)
        # База = min(25000, 3028) = 3028; 3028 × 1.1% = 33.31.
        self.assertAlmostEqual(acc.amount, 33.31, places=2)
        self.assertAlmostEqual(acc.rate, 1.1, places=1)

    def test_payslip_indexation_prorated(self):
        slip = self._payslip(date(2025, 3, 31), worked=10, scheduled=20)
        slip._generate_accruals()
        acc = self._indexation(slip)
        # 3028 × 1.1% × 10/20 = 16.65.
        self.assertAlmostEqual(acc.amount, 16.65, places=2)

    def test_no_indexation_when_disabled(self):
        self.version.indexation_enabled = False
        slip = self._payslip(date(2025, 3, 31))
        slip._generate_accruals()
        self.assertFalse(self._indexation(slip))

    def test_no_indexation_without_base_month(self):
        self.version.indexation_base_month = False
        slip = self._payslip(date(2025, 3, 31))
        slip._generate_accruals()
        self.assertFalse(self._indexation(slip))

    def test_no_indexation_below_threshold(self):
        # 02.2025 — поріг не перевищено, нарахування немає.
        slip = self._payslip(date(2025, 2, 28))
        slip._generate_accruals()
        self.assertFalse(self._indexation(slip))
