"""Тести ретро-перерахунків зарплати за закриті періоди (#151).

Механізм recompute-and-diff: закритий листок перераховується з поточними
даними (оклад/табель), різниця валового доходу переноситься окремим рядком
«Перерахунок» у поточний чернетковий листок; ПДФО/ВЗ/ЄСВ на дельту
перераховуються автоматично.
"""

from datetime import date

from .common import SalaryTestCase
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestRetroRecalc(SalaryTestCase):

    def _done_payslip(self):
        """Закритий червневий листок з окладом 25000 → gross 25000."""
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        })
        slip.action_compute_sheet()
        slip.write({'state': 'done'})
        return slip

    def _draft_current(self):
        """Порожній липневий чернетковий листок (без власного окладу)."""
        return self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 7, 1),
            'date_to': date(2025, 7, 31),
        })

    def _retro_line(self, target):
        return target.accrual_ids.filtered(
            lambda a: a.accrual_type_id.code == 'RETRO')

    def test_wage_increase_carries_positive_delta(self):
        source = self._done_payslip()
        self.assertAlmostEqual(source.gross_salary, 25000.0, places=2)
        target = self._draft_current()
        # Ретроактивне підвищення окладу.
        self.version.wage = 30000.0
        source.action_retro_recalculate()
        line = self._retro_line(target)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.amount, 5000.0, places=2)

    def test_taxes_recomputed_on_delta(self):
        source = self._done_payslip()
        target = self._draft_current()
        self.version.wage = 30000.0
        source.action_retro_recalculate()
        # Єдине нарахування в цільовому — ретро 5000; ВЗ без ПСП = 5%.
        self.assertAlmostEqual(target.gross_salary, 5000.0, places=2)
        self.assertAlmostEqual(target.military_tax_amount, 250.0, places=2)
        # ПДФО з урахуванням ПСП, але > 0 — податок на дельту нарахований.
        self.assertGreater(target.pdfo_amount, 0.0)

    def test_wage_decrease_is_storno(self):
        source = self._done_payslip()
        target = self._draft_current()
        self.version.wage = 22000.0
        source.action_retro_recalculate()
        line = self._retro_line(target)
        self.assertAlmostEqual(line.amount, -3000.0, places=2)

    def test_no_change_no_line(self):
        source = self._done_payslip()
        target = self._draft_current()
        source.action_retro_recalculate()
        self.assertFalse(self._retro_line(target))
        self.assertFalse(target.retro_incoming_ids)

    def test_idempotent_rerun(self):
        source = self._done_payslip()
        target = self._draft_current()
        self.version.wage = 30000.0
        source.action_retro_recalculate()
        source.action_retro_recalculate()
        line = self._retro_line(target)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.amount, 5000.0, places=2)
        self.assertEqual(len(target.retro_incoming_ids), 1)

    def test_rerun_updates_delta_after_second_change(self):
        source = self._done_payslip()
        target = self._draft_current()
        self.version.wage = 30000.0
        source.action_retro_recalculate()
        # Другий перегляд окладу — дельта має оновитись, не додатись.
        self.version.wage = 28000.0
        source.action_retro_recalculate()
        line = self._retro_line(target)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.amount, 3000.0, places=2)

    def test_audit_record_created(self):
        source = self._done_payslip()
        target = self._draft_current()
        self.version.wage = 30000.0
        source.action_retro_recalculate()
        retro = source.retro_source_ids
        self.assertEqual(len(retro), 1)
        self.assertAlmostEqual(retro.old_gross, 25000.0, places=2)
        self.assertAlmostEqual(retro.new_gross, 30000.0, places=2)
        self.assertAlmostEqual(retro.gross_delta, 5000.0, places=2)
        self.assertEqual(retro.target_payslip_id, target)

    def test_source_must_be_done(self):
        source = self._done_payslip()
        source.write({'state': 'draft'})
        self._draft_current()
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            source.action_retro_recalculate()

    def test_no_target_raises(self):
        source = self._done_payslip()
        from odoo.exceptions import UserError
        with self.assertRaises(UserError):
            source.action_retro_recalculate()
