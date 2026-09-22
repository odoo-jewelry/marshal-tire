from odoo import models, fields


class HrTimesheetCode(models.Model):
    _name = 'hr.timesheet.code'
    _description = 'Timesheet Code'
    _order = 'sequence, code'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, size=3)
    sequence = fields.Integer(string='Sequence', default=10)
    
    code_type = fields.Selection([
        ('work', 'Work'),
        ('absence', 'Absence'),
        ('leave', 'Leave'),
        ('sick', 'Sick Leave'),
        ('holiday', 'Holiday'),
        ('other', 'Other'),
    ], string='Type', required=True, default='work')
    
    is_worked = fields.Boolean(
        string='Counted as Worked',
        help='Hours are counted as worked time'
    )
    is_paid = fields.Boolean(
        string='Paid',
        default=True
    )
    default_hours = fields.Float(
        string='Default Hours',
        default=8.0
    )
    
    color = fields.Integer(string='Color')
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _unique_code = models.Constraint(
        'unique(code)',
        'Timesheet code must be unique!',
    )
