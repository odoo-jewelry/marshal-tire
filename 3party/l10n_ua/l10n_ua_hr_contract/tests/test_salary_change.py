"""Tests for salary change workflow — HR-5 from HR_UKRAINE.md.

Tests cover:
- Salary change creation
- Computed fields (change_amount, change_percent)
- State workflow (draft -> confirmed -> applied -> cancelled)
- Apply action updates version wage
"""

from datetime import date
from odoo.tests import tagged
from .common import ContractTestCase


@tagged('post_install', '-at_install')
class TestSalaryChange(ContractTestCase):
    """Test hr.version.salary.change workflow."""

    def _create_salary_change(self, version=None, **kwargs):
        if version is None:
            version = self._create_version(wage=20000)
        vals = {
            'version_id': version.id,
            'old_wage': 20000,
            'new_wage': 25000,
            'effective_date': date(2025, 7, 1),
            'order_number': 'НК-001/2025',
            'order_date': date(2025, 6, 25),
            'reason': 'Підвищення кваліфікації',
        }
        vals.update(kwargs)
        return self.env['hr.version.salary.change'].create(vals)

    def test_salary_change_creation(self):
        """Salary change should be created in draft state."""
        sc = self._create_salary_change()
        self.assertEqual(sc.state, 'draft')
        self.assertTrue(sc.name)

    def test_change_amount_computed(self):
        """Change amount = new_wage - old_wage."""
        sc = self._create_salary_change(old_wage=20000, new_wage=25000)
        self.assertEqual(sc.change_amount, 5000)

    def test_change_percent_computed(self):
        """Change percent = (new - old) / old * 100."""
        sc = self._create_salary_change(old_wage=20000, new_wage=25000)
        self.assertAlmostEqual(sc.change_percent, 25.0, places=1)

    def test_salary_change_confirm(self):
        """Confirm action should move to confirmed state."""
        sc = self._create_salary_change()
        sc.action_confirm()
        self.assertEqual(sc.state, 'confirmed')

    def test_salary_change_apply(self):
        """Apply action should update version wage."""
        version = self._create_version(wage=20000)
        sc = self._create_salary_change(version=version, old_wage=20000, new_wage=25000)
        sc.action_confirm()
        sc.action_apply()
        self.assertEqual(sc.state, 'applied')
        version.invalidate_recordset()
        self.assertEqual(version.wage, 25000)

    def test_salary_change_cancel(self):
        """Cancel action should set state to cancelled."""
        sc = self._create_salary_change()
        sc.action_confirm()
        sc.action_cancel()
        self.assertEqual(sc.state, 'cancelled')

    def test_salary_change_draft_reset(self):
        """Draft action should reset state to draft."""
        sc = self._create_salary_change()
        sc.action_confirm()
        sc.action_cancel()
        sc.action_draft()
        self.assertEqual(sc.state, 'draft')

    def test_salary_decrease(self):
        """Salary decrease should show negative change."""
        sc = self._create_salary_change(old_wage=30000, new_wage=25000)
        self.assertEqual(sc.change_amount, -5000)
        self.assertAlmostEqual(sc.change_percent, -16.67, places=1)
