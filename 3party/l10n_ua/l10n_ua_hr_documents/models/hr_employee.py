from odoo import models, fields, api


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    order_ids = fields.One2many(
        'hr.order',
        'employee_id',
        string='HR Orders'
    )
    orders_count = fields.Integer(
        string='Orders',
        compute='_compute_orders_count'
    )

    def _compute_orders_count(self):
        for employee in self:
            employee.orders_count = self.env['hr.order'].search_count([
                ('employee_id', '=', employee.id)
            ])

    def action_create_order(self):
        """Open wizard to create a new HR order for this employee"""
        self.ensure_one()
        ctx = {
            'default_employee_id': self.id,
        }
        if self.department_id:
            ctx['default_department_id'] = self.department_id.id
        if self.job_id:
            ctx['default_job_id'] = self.job_id.id
        if self.company_id:
            ctx['default_company_id'] = self.company_id.id
        return {
            'name': 'Новий наказ',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.order',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }

    def action_view_orders(self):
        """View all orders for this employee"""
        self.ensure_one()
        ctx = {
            'default_employee_id': self.id,
        }
        if self.department_id:
            ctx['default_department_id'] = self.department_id.id
        if self.job_id:
            ctx['default_job_id'] = self.job_id.id
        return {
            'name': f'Накази: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.order',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': ctx,
        }
