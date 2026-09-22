"""Тести депонування заробітної плати (#155)."""

from datetime import date

from .common import SalaryTestCase
from odoo.tests import tagged
from odoo.exceptions import UserError, ValidationError


@tagged('post_install', '-at_install')
class TestSalaryDeposit(SalaryTestCase):

    def _done_payslip(self):
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        })
        slip.action_compute_sheet()
        slip.write({'state': 'done'})
        return slip

    def _deposit(self, slip):
        slip.action_deposit_unpaid()
        return slip.deposit_ids

    def test_deposit_from_payslip(self):
        slip = self._done_payslip()
        dep = self._deposit(slip)
        self.assertEqual(len(dep), 1)
        self.assertAlmostEqual(dep.amount, slip.net_salary, places=2)
        self.assertEqual(dep.state, 'deposited')
        self.assertAlmostEqual(dep.residual, slip.net_salary, places=2)
        self.assertTrue(dep.name.startswith('ДЕП/'))

    def test_partial_payment(self):
        slip = self._done_payslip()
        dep = self._deposit(slip)
        self.env['hr.salary.deposit.payment'].create({
            'deposit_id': dep.id, 'amount': 1000.0})
        self.assertEqual(dep.state, 'partial')
        self.assertAlmostEqual(dep.paid_amount, 1000.0, places=2)
        self.assertAlmostEqual(dep.residual, dep.amount - 1000.0, places=2)

    def test_full_payment_via_action(self):
        slip = self._done_payslip()
        dep = self._deposit(slip)
        dep.action_pay_full()
        self.assertEqual(dep.state, 'paid')
        self.assertAlmostEqual(dep.residual, 0.0, places=2)
        self.assertAlmostEqual(dep.paid_amount, dep.amount, places=2)

    def test_overpay_raises(self):
        slip = self._done_payslip()
        dep = self._deposit(slip)
        with self.assertRaises(ValidationError):
            self.env['hr.salary.deposit.payment'].create({
                'deposit_id': dep.id, 'amount': dep.amount + 100.0})

    def test_duplicate_deposit_raises(self):
        slip = self._done_payslip()
        self._deposit(slip)
        with self.assertRaises(UserError):
            slip.action_deposit_unpaid()

    def test_deposit_requires_done(self):
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        })
        with self.assertRaises(UserError):
            slip.action_deposit_unpaid()

    def test_employee_residual(self):
        slip = self._done_payslip()
        dep = self._deposit(slip)
        self.employee.invalidate_recordset(['salary_deposit_residual'])
        self.assertAlmostEqual(
            self.employee.salary_deposit_residual, dep.amount, places=2)
        # Після повної виплати залишок = 0.
        dep.action_pay_full()
        self.employee.invalidate_recordset(['salary_deposit_residual'])
        self.assertAlmostEqual(self.employee.salary_deposit_residual, 0.0, places=2)
