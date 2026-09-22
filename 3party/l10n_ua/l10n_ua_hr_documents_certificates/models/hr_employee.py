from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    certificate_ids = fields.One2many(
        'hr.certificate',
        'employee_id',
        string='Certificates'
    )
    certificates_count = fields.Integer(
        string='Certificates Count',
        compute='_compute_certificates_count'
    )

    def _compute_certificates_count(self):
        for employee in self:
            employee.certificates_count = len(employee.certificate_ids)

    def action_open_certificates(self):
        """Open certificates for this employee"""
        self.ensure_one()
        return {
            'name': f'Довідки: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.certificate',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }

    def action_create_certificate(self):
        """Open form to create a new certificate for this employee"""
        self.ensure_one()
        ctx = {
            'default_employee_id': self.id,
        }
        if self.company_id:
            ctx['default_company_id'] = self.company_id.id
        return {
            'name': 'Нова довідка',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.certificate',
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }
