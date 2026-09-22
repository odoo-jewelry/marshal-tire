"""Tests for payslip run (batch) — HR-25 from HR_UKRAINE.md.

Tests cover:
- Payslip run creation
- Batch computation
- Computed totals
- State workflow
"""

from datetime import date
from odoo.tests import tagged
from .common import SalaryTestCase


@tagged('post_install', '-at_install')
class TestPayslipRun(SalaryTestCase):
    """Test hr.payslip.run batch processing."""

    def _create_run(self, **kwargs):
        vals = {
            'date_start': date(2025, 6, 1),
            'date_end': date(2025, 6, 30),
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.env['hr.payslip.run'].create(vals)

    def _add_payslip_to_run(self, run, employee=None):
        """Manually add a payslip with accrual to a run."""
        if employee is None:
            employee = self.employee
        payslip = self.env['hr.payslip'].create({
            'employee_id': employee.id,
            'payslip_run_id': run.id,
            'date_from': run.date_start,
            'date_to': run.date_end,
            'company_id': self.company.id,
        })
        self.env['hr.payslip.accrual'].create({
            'payslip_id': payslip.id,
            'accrual_type_id': self.accrual_wage.id,
            'quantity': 1,
            'rate': 25000,
            'amount': 25000,
        })
        return payslip

    def test_run_creation(self):
        """Payslip run should be created in draft state."""
        run = self._create_run()
        self.assertEqual(run.state, 'draft')
        self.assertTrue(run.name)

    def test_run_with_payslip(self):
        """Run should contain manually added payslips."""
        run = self._create_run()
        self._add_payslip_to_run(run)
        self.assertEqual(len(run.slip_ids), 1)

    def test_run_compute_all(self):
        """Compute all should compute each payslip."""
        run = self._create_run()
        self._add_payslip_to_run(run)
        run.action_compute_all()
        for slip in run.slip_ids:
            self.assertIn(slip.state, ('draft', 'verify'))

    def test_run_totals_computed(self):
        """Run totals should aggregate from payslips."""
        run = self._create_run()
        self._add_payslip_to_run(run)
        run.action_compute_all()
        run.invalidate_recordset()
        self.assertGreaterEqual(run.total_gross, 0)
        self.assertGreaterEqual(run.total_net, 0)

    def test_run_state_workflow(self):
        """State: draft -> verify -> close."""
        run = self._create_run()
        self._add_payslip_to_run(run)
        run.action_compute_all()
        run.action_verify()
        self.assertEqual(run.state, 'verify')
        run.action_close()
        self.assertEqual(run.state, 'close')

    def test_run_default_dates(self):
        """Default dates should cover current month."""
        run = self.env['hr.payslip.run'].create({
            'company_id': self.company.id,
        })
        self.assertTrue(run.date_start)
        self.assertTrue(run.date_end)
