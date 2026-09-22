"""Multi-company isolation для hr.bonus (#26)."""

from datetime import date
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBonusMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Company B'})
        cls.employee_a = cls.env['hr.employee'].create({
            'name': 'Emp A', 'company_id': cls.company_a.id,
            'bonus_system_enabled': True,
        })
        cls.bonus_type = cls.env['hr.bonus.type'].search([], limit=1) or \
            cls.env['hr.bonus.type'].create({'name': 'Test', 'code': 'TEST'})

    def test_onchange_company_resets_cross_company_employee(self):
        bonus = self.env['hr.bonus'].new({
            'company_id': self.company_a.id,
            'employee_id': self.employee_a.id,
            'bonus_type_id': self.bonus_type.id,
            'date': date(2026, 4, 20),
            'amount': 1000.0,
        })
        bonus.company_id = self.company_b
        bonus._onchange_company_id()
        self.assertFalse(bonus.employee_id)

    def test_onchange_company_keeps_same_company_employee(self):
        bonus = self.env['hr.bonus'].new({
            'company_id': self.company_a.id,
            'employee_id': self.employee_a.id,
            'bonus_type_id': self.bonus_type.id,
            'date': date(2026, 4, 20),
            'amount': 500.0,
        })
        bonus._onchange_company_id()
        self.assertEqual(bonus.employee_id, self.employee_a)
