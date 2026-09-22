from datetime import date
from odoo.tests.common import TransactionCase


class TestHrSickLeave(TransactionCase):
    """Tests for hr.sick.leave model"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Employee',
            'company_id': cls.company.id,
        })

    def test_sick_leave_creation(self):
        """Test sick leave creation with basic fields"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
            'sick_leave_number': 'SL-001',
        })
        self.assertEqual(sick_leave.employee_id, self.employee)
        self.assertEqual(sick_leave.sick_leave_type, 'illness')
        self.assertEqual(sick_leave.sick_leave_number, 'SL-001')

    def test_sick_leave_types(self):
        """Test all sick leave types"""
        types = ['illness', 'injury', 'pregnancy', 'quarantine', 
                 'prosthetics', 'sanatorium', 'child_care']
        for sick_type in types:
            sick_leave = self.env['hr.sick.leave'].create({
                'employee_id': self.employee.id,
                'date_from': date(2026, 1, 15),
                'date_to': date(2026, 1, 21),
                'sick_leave_type': sick_type,
            })
            self.assertEqual(sick_leave.sick_leave_type, sick_type)

    def test_sick_leave_electronic(self):
        """Test electronic sick leave (e-TVN)"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
            'is_electronic': True,
            'e_sick_leave_id': 'E-TVN-12345',
        })
        self.assertTrue(sick_leave.is_electronic)
        self.assertEqual(sick_leave.e_sick_leave_id, 'E-TVN-12345')

    def test_calendar_days_computation(self):
        """Test calendar days calculation"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
        })
        self.assertEqual(sick_leave.calendar_days, 7)

    def test_payment_percent_by_experience(self):
        """Test payment percent based on insurance experience"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
            'insurance_experience_years': 2,
        })
        self.assertEqual(sick_leave.payment_percent, 50)
        
        sick_leave.insurance_experience_years = 4
        self.assertEqual(sick_leave.payment_percent, 60)
        
        sick_leave.insurance_experience_years = 6
        self.assertEqual(sick_leave.payment_percent, 70)
        
        sick_leave.insurance_experience_years = 10
        self.assertEqual(sick_leave.payment_percent, 100)

    def test_payment_percent_pregnancy(self):
        """Test that pregnancy always gets 100% payment"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'pregnancy',
            'insurance_experience_years': 1,
        })
        self.assertEqual(sick_leave.payment_percent, 100)

    def test_employer_and_fss_days(self):
        """Test employer days (first 5) and FSS days calculation"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
        })
        self.assertEqual(sick_leave.employer_days, 5)
        self.assertEqual(sick_leave.fss_days, 2)

    def test_short_sick_leave_employer_only(self):
        """Test short sick leave (<=5 days) paid only by employer.

        Межа: рівно 5 календарних днів (15–19 січня) → усі 5 оплачує
        роботодавець, ФСС — 0 (employer_days = min(5, calendar_days)).
        """
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 19),
            'sick_leave_type': 'illness',
        })
        self.assertEqual(sick_leave.calendar_days, 5)
        self.assertEqual(sick_leave.employer_days, 5)
        self.assertEqual(sick_leave.fss_days, 0)

    def test_pregnancy_fss_only(self):
        """Test pregnancy sick leave paid entirely by FSS"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 5, 15),
            'sick_leave_type': 'pregnancy',
        })
        self.assertEqual(sick_leave.fss_days, sick_leave.calendar_days)

    def test_sick_leave_states(self):
        """Test sick leave state transitions (without hr.leave creation)"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
        })
        self.assertEqual(sick_leave.state, 'draft')
        
        sick_leave.action_pay()
        self.assertEqual(sick_leave.state, 'paid')

    def test_sick_leave_cancel(self):
        """Test sick leave cancellation"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
        })
        sick_leave.action_cancel()
        self.assertEqual(sick_leave.state, 'cancelled')
        
        sick_leave.action_draft()
        self.assertEqual(sick_leave.state, 'draft')

    def test_total_amount_calculation(self):
        """Test total amount = employer_amount + fss_amount"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
            'average_daily_salary': 500.0,
            'insurance_experience_years': 10,
        })
        
        expected_employer = 5 * 500.0
        expected_fss = 2 * 500.0
        self.assertEqual(sick_leave.employer_amount, expected_employer)
        self.assertEqual(sick_leave.fss_amount, expected_fss)
        self.assertEqual(sick_leave.total_amount, expected_employer + expected_fss)

    def test_date_validation(self):
        """Test that date_from must be before date_to"""
        from odoo.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.env['hr.sick.leave'].create({
                'employee_id': self.employee.id,
                'date_from': date(2026, 1, 21),
                'date_to': date(2026, 1, 15),
                'sick_leave_type': 'illness',
            })

    def test_auto_sequence(self):
        """Test automatic sequence generation for name"""
        sick_leave = self.env['hr.sick.leave'].create({
            'employee_id': self.employee.id,
            'date_from': date(2026, 1, 15),
            'date_to': date(2026, 1, 21),
            'sick_leave_type': 'illness',
        })
        self.assertNotEqual(sick_leave.name, 'New')
