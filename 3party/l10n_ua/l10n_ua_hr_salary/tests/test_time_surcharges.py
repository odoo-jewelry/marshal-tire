"""Тести авто-доплат за відхилення в табелі (#143).

Нічні / понаднормові / святкові рахуються зверху базового окладу:
- нічні = години × годинна ставка × %;
- понаднормові/святкові = години × ставка × (множник − 1) (доплата до ×N).
"""

from datetime import date

from .common import SalaryTestCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestTimeSurcharges(SalaryTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Детермінований годинний тариф: оклад 25000 / 160 год = 156.25.
        cls.psp_params.write({
            'min_hourly_wage': 0.0,
            'night_surcharge_rate': 20.0,
            'overtime_multiplier': 2.0,
            'holiday_multiplier': 2.0,
        })
        for code, name in [('NIGHT', 'Нічні'), ('OVERTIME', 'Понаднормові'),
                           ('HOLIDAY', 'Святкові')]:
            if not cls.env['hr.accrual.type'].search([('code', '=', code)], limit=1):
                cls.env['hr.accrual.type'].create({
                    'name': name, 'code': code, 'category': 'allowance'})

    def _payslip(self, **kw):
        vals = {
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        }
        vals.update(kw)
        slip = self.env['hr.payslip'].create(vals)
        # Симулюємо табель: норма 160 год, 20/20 днів.
        slip.write({
            'scheduled_hours': 160.0, 'scheduled_days': 20, 'worked_days': 20,
            'worked_hours': 160.0,
        })
        return slip

    def _accrual(self, slip, code):
        return slip.accrual_ids.filtered(
            lambda a: a.accrual_type_id.code == code)

    def test_night_surcharge(self):
        slip = self._payslip(night_hours=10.0)
        slip._generate_accruals()
        acc = self._accrual(slip, 'NIGHT')
        self.assertEqual(len(acc), 1)
        # 10 × 156.25 × 20% = 312.50
        self.assertAlmostEqual(acc.amount, 312.50, places=2)

    def test_overtime_surcharge(self):
        slip = self._payslip(overtime_hours=5.0)
        slip._generate_accruals()
        acc = self._accrual(slip, 'OVERTIME')
        # 5 × 156.25 × (2−1) = 781.25
        self.assertAlmostEqual(acc.amount, 781.25, places=2)

    def test_holiday_surcharge(self):
        slip = self._payslip(holiday_hours=4.0)
        slip._generate_accruals()
        acc = self._accrual(slip, 'HOLIDAY')
        # 4 × 156.25 × (2−1) = 625.00
        self.assertAlmostEqual(acc.amount, 625.00, places=2)

    def test_no_hours_no_surcharge(self):
        slip = self._payslip()
        slip._generate_accruals()
        self.assertFalse(self._accrual(slip, 'NIGHT'))
        self.assertFalse(self._accrual(slip, 'OVERTIME'))
        self.assertFalse(self._accrual(slip, 'HOLIDAY'))

    def test_surcharges_are_auto_regenerated(self):
        slip = self._payslip(night_hours=10.0)
        slip._generate_accruals()
        first = self._accrual(slip, 'NIGHT')
        self.assertTrue(first.is_auto_generated)
        # Повторна генерація не дублює.
        slip._generate_accruals()
        self.assertEqual(len(self._accrual(slip, 'NIGHT')), 1)
