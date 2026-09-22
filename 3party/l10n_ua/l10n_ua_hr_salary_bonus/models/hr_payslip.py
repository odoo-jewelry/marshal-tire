from odoo import models, api


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _generate_accruals(self):
        """Extend accrual generation to include bonuses."""
        super()._generate_accruals()

        for payslip in self:
            payslip._generate_bonus_accruals()

    def _generate_bonus_accruals(self):
        """Generate accrual lines for confirmed bonuses."""
        self.ensure_one()

        # Check if employee has bonus system enabled
        if not self.employee_id.bonus_system_enabled:
            return

        # Find confirmed bonuses for this period
        bonuses = self.env['hr.bonus'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', '=', 'confirmed'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('payslip_id', '=', False),  # Not yet linked to a payslip
        ])

        if not bonuses:
            return

        # Get BONUS accrual type
        accrual_type = self.env['hr.accrual.type'].search([
            ('code', '=', 'BONUS')
        ], limit=1)

        if not accrual_type:
            return

        for bonus in bonuses:
            # Create accrual line
            self.env['hr.payslip.accrual'].create({
                'payslip_id': self.id,
                'accrual_type_id': accrual_type.id,
                'quantity': 1,
                'rate': bonus.amount,
                'amount': bonus.amount,
                'notes': f"{bonus.bonus_type_id.name}: {bonus.name}",
            })

            # Link bonus to payslip
            bonus.payslip_id = self.id

    def action_payslip_done(self):
        """Override to mark linked bonuses as paid."""
        res = super().action_payslip_done()

        # Mark linked bonuses as paid
        bonuses = self.env['hr.bonus'].search([
            ('payslip_id', 'in', self.ids),
            ('state', '=', 'confirmed'),
        ])
        if bonuses:
            bonuses.write({'state': 'paid'})

        return res

    def action_payslip_cancel(self):
        """Override to unlink bonuses when payslip is cancelled."""
        # Get linked bonuses before cancelling
        bonuses = self.env['hr.bonus'].search([
            ('payslip_id', 'in', self.ids),
        ])

        res = super().action_payslip_cancel()

        # Reset bonuses to confirmed state and unlink from payslip
        if bonuses:
            bonuses.write({
                'state': 'confirmed',
                'payslip_id': False,
            })

        return res
