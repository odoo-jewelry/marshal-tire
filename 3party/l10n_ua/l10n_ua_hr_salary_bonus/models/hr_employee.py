from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    bonus_system_enabled = fields.Boolean(
        string='Bonus System Enabled',
        default=False,
        help='Enable bonus system for this employee. When enabled, confirmed bonuses will be included in payroll calculation.',
    )
    bonus_ids = fields.One2many(
        'hr.bonus',
        'employee_id',
        string='Bonuses',
    )
    bonus_count = fields.Integer(
        string='Bonus Count',
        compute='_compute_bonus_count',
    )

    @api.depends('bonus_ids')
    def _compute_bonus_count(self):
        for employee in self:
            employee.bonus_count = len(employee.bonus_ids)

    def action_open_bonuses(self):
        """Open bonus list for this employee."""
        self.ensure_one()
        return {
            'name': 'Bonuses',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.bonus',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }
