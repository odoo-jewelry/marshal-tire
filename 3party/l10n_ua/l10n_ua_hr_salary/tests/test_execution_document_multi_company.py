"""Multi-company isolation для hr.execution.document (#26)."""

from datetime import date
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestExecutionDocumentMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Company B'})
        cls.employee_a = cls.env['hr.employee'].create({
            'name': 'Emp A', 'company_id': cls.company_a.id,
        })

    def test_onchange_company_resets_cross_company_employee(self):
        doc = self.env['hr.execution.document'].new({
            'name': 'DOC-001',
            'company_id': self.company_a.id,
            'employee_id': self.employee_a.id,
            'document_type': 'alimony',
            'date_from': date(2026, 4, 1),
        })
        doc.company_id = self.company_b
        doc._onchange_company_id()
        self.assertFalse(doc.employee_id)

    def test_onchange_company_keeps_same_company_employee(self):
        doc = self.env['hr.execution.document'].new({
            'name': 'DOC-002',
            'company_id': self.company_a.id,
            'employee_id': self.employee_a.id,
            'document_type': 'alimony',
            'date_from': date(2026, 4, 1),
        })
        doc._onchange_company_id()
        self.assertEqual(doc.employee_id, self.employee_a)
