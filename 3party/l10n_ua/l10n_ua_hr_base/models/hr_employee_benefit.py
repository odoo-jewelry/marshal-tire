from odoo import models, fields


class HrEmployeeBenefit(models.Model):
    _name = 'hr.employee.benefit'
    _description = 'Employee Benefit Type'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    description = fields.Text(string='Description')
    psp_type = fields.Selection([
        ('none', 'No PSP'),
        ('standard', 'Standard (50%)'),
        ('150', 'Increased (150%)'),
        ('200', 'Maximum (200%)'),
    ], string='PSP Type', default='none',
       help='Type of Personal Income Tax Social Benefit (PSP)')
    psp_multiplier = fields.Float(string='PSP Multiplier', default=0.0)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _code_uniq = models.Constraint(
        'unique(code)',
        'Benefit code must be unique!',
    )
