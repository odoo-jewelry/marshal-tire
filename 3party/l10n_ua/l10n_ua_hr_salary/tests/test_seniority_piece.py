"""Tests for the automatic seniority bonus and piece-rate pay (#143)."""

from datetime import date

from .common import SalaryTestCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestSeniorityPiece(SalaryTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.psp_params.write({'min_hourly_wage': 0.0})
        for code, name, cat in [('SENIORITY', 'Seniority bonus', 'allowance'),
                                ('PIECE', 'Piece rate', 'wage')]:
            if not cls.env['hr.accrual.type'].search([('code', '=', code)], limit=1):
                cls.env['hr.accrual.type'].create({
                    'name': name, 'code': code, 'category': cat})
        # Own scale: 10% from one year of service, 25% from ten.
        cls.scale = cls.env['hr.seniority.scale'].create({
            'name': 'Test scale',
            'company_id': cls.company.id,
            'line_ids': [(0, 0, {'years_from': 1, 'percent': 10}),
                         (0, 0, {'years_from': 10, 'percent': 25})],
        })

    def _payslip(self, **kw):
        vals = {
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        }
        vals.update(kw)
        slip = self.env['hr.payslip'].create(vals)
        slip.write({
            'scheduled_hours': 160.0, 'scheduled_days': 20, 'worked_days': 20,
            'worked_hours': 160.0,
        })
        return slip

    def _accrual(self, slip, code):
        return slip.accrual_ids.filtered(lambda a: a.accrual_type_id.code == code)

    # --- Seniority scale ---

    def test_scale_get_percent(self):
        self.assertEqual(self.scale.get_percent(0), 0.0)
        self.assertEqual(self.scale.get_percent(5), 10.0)
        self.assertEqual(self.scale.get_percent(12), 25.0)

    def test_seniority_accrual_full_month(self):
        # Experience comes from the native contract date; hire_date derives
        # from it.
        self.version.contract_date_start = date(2010, 1, 1)  # over 10 years -> 25%
        self.assertEqual(self.employee.hire_date, date(2010, 1, 1))
        self.version.write({
            'seniority_enabled': True, 'seniority_scale_id': self.scale.id})
        slip = self._payslip()
        slip._generate_accruals()
        acc = self._accrual(slip, 'SENIORITY')
        self.assertEqual(len(acc), 1)
        # 25000 * 25% = 6250
        self.assertAlmostEqual(acc.amount, 6250.0, places=2)
        self.assertEqual(acc.rate, 25.0)

    def test_seniority_at_payslip_date_not_today(self):
        """The rate follows the experience at period end, not "today"."""
        self.version.contract_date_start = date(2024, 8, 1)
        self.version.write({
            'seniority_enabled': True, 'seniority_scale_id': self.scale.id})

        # Period ending before the first anniversary -> no bonus.
        early = self._payslip(date_from=date(2025, 3, 1), date_to=date(2025, 3, 31))
        early._generate_accruals()
        self.assertFalse(self._accrual(early, 'SENIORITY'))

        # Period after the anniversary -> 10%.
        later = self._payslip(date_from=date(2025, 9, 1), date_to=date(2025, 9, 30))
        later._generate_accruals()
        acc = self._accrual(later, 'SENIORITY')
        self.assertEqual(len(acc), 1)
        self.assertEqual(acc.rate, 10.0)

    def test_seniority_prorated(self):
        self.version.contract_date_start = date(2020, 1, 1)  # over 1 year -> 10%
        self.version.write({
            'seniority_enabled': True, 'seniority_scale_id': self.scale.id})
        slip = self._payslip()
        slip.write({'worked_days': 10})  # half of the month
        slip._generate_accruals()
        acc = self._accrual(slip, 'SENIORITY')
        # 25000 * 10% * 10/20 = 1250
        self.assertAlmostEqual(acc.amount, 1250.0, places=2)

    def test_seniority_disabled(self):
        self.version.write({'seniority_enabled': False})
        slip = self._payslip()
        slip._generate_accruals()
        self.assertFalse(self._accrual(slip, 'SENIORITY'))

    # --- Piece-rate pay ---

    def test_piece_work_accrual(self):
        self.version.write({'salary_form': 'piece'})
        Entry = self.env['hr.piece.work.entry']
        Entry.create({
            'name': 'Operation A', 'employee_id': self.employee.id,
            'date': date(2025, 6, 10), 'quantity': 100, 'unit_rate': 5,
            'company_id': self.company.id})
        Entry.create({
            'name': 'Operation B', 'employee_id': self.employee.id,
            'date': date(2025, 6, 20), 'quantity': 50, 'unit_rate': 4,
            'company_id': self.company.id})
        slip = self._payslip()
        slip._generate_accruals()
        acc = self._accrual(slip, 'PIECE')
        self.assertEqual(len(acc), 1)
        # 100*5 + 50*4 = 700
        self.assertAlmostEqual(acc.amount, 700.0, places=2)
        self.assertAlmostEqual(acc.quantity, 150.0, places=2)
        # Piece-rate replaces the wage, so SALARY is not accrued.
        self.assertFalse(self._accrual(slip, 'SALARY'))

    def test_piece_excludes_other_period(self):
        self.version.write({'salary_form': 'piece'})
        self.env['hr.piece.work.entry'].create({
            'name': 'May work order', 'employee_id': self.employee.id,
            'date': date(2025, 5, 31), 'quantity': 100, 'unit_rate': 5,
            'company_id': self.company.id})
        slip = self._payslip()
        slip._generate_accruals()
        # An entry outside the payslip period is not picked up.
        self.assertFalse(self._accrual(slip, 'PIECE'))

    def test_piece_skips_surcharges(self):
        self.version.write({'salary_form': 'piece'})
        slip = self._payslip(night_hours=10.0)
        slip._generate_accruals()
        # Surcharges derived from the monthly wage do not apply to piece-rate.
        self.assertFalse(self._accrual(slip, 'NIGHT'))
