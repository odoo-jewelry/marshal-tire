"""Tests for execution documents — HR-26 from HR_UKRAINE.md.

Tests cover:
- Execution document creation
- Document types (alimony, court, tax debt)
- Calculation methods
- State workflow (draft -> active -> suspended -> closed)
"""

from datetime import date
from odoo.tests import tagged
from .common import SalaryTestCase


@tagged('post_install', '-at_install')
class TestExecutionDocument(SalaryTestCase):
    """Test hr.execution.document model."""

    def _create_exec_doc(self, **kwargs):
        vals = {
            'name': 'ВД-001/2025',
            'employee_id': self.employee.id,
            'document_type': 'alimony',
            'calculation_method': 'percent',
            'percent_value': 25.0,
            'date_from': date(2025, 1, 1),
            'recipient_name': 'Петренко Марія Іванівна',
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.env['hr.execution.document'].create(vals)

    def test_exec_doc_creation(self):
        """Execution document should be created in draft state."""
        doc = self._create_exec_doc()
        self.assertEqual(doc.state, 'draft')
        self.assertTrue(doc.name)

    def test_exec_doc_types(self):
        """All document types should be valid."""
        for i, dtype in enumerate(['alimony', 'court_decision', 'tax_debt', 'other_debt']):
            doc = self._create_exec_doc(
                name=f'ВД-{i:03d}/2025',
                document_type=dtype,
            )
            self.assertEqual(doc.document_type, dtype)

    def test_exec_doc_percent_method(self):
        """Percent method should store percent value."""
        doc = self._create_exec_doc(
            calculation_method='percent',
            percent_value=25.0,
        )
        self.assertEqual(doc.percent_value, 25.0)

    def test_exec_doc_fixed_method(self):
        """Fixed method should store fixed amount."""
        doc = self._create_exec_doc(
            name='ВД-002/2025',
            calculation_method='fixed',
            fixed_amount=5000,
        )
        self.assertEqual(doc.fixed_amount, 5000)

    def test_exec_doc_activate(self):
        """Activate should move to active state."""
        doc = self._create_exec_doc()
        doc.action_activate()
        self.assertEqual(doc.state, 'active')

    def test_exec_doc_suspend(self):
        """Suspend should move to suspended state."""
        doc = self._create_exec_doc()
        doc.action_activate()
        doc.action_suspend()
        self.assertEqual(doc.state, 'suspended')

    def test_exec_doc_close(self):
        """Close should move to closed state."""
        doc = self._create_exec_doc(name='ВД-003/2025')
        doc.action_activate()
        doc.action_close()
        self.assertEqual(doc.state, 'closed')

    def test_exec_doc_draft_reset(self):
        """Draft should reset from suspended."""
        doc = self._create_exec_doc(name='ВД-004/2025')
        doc.action_activate()
        doc.action_suspend()
        doc.action_draft()
        self.assertEqual(doc.state, 'draft')

    def test_alimony_percent(self):
        """Alimony at 25% is a standard rate."""
        doc = self._create_exec_doc(
            name='ВД-005/2025',
            document_type='alimony',
            calculation_method='percent',
            percent_value=25.0,
        )
        self.assertEqual(doc.document_type, 'alimony')
        self.assertEqual(doc.percent_value, 25.0)
