from odoo import models, fields


class HrAllowanceType(models.Model):
    _name = 'hr.allowance.type'
    _description = 'Allowance Type'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    category = fields.Selection([
        ('seniority', 'Seniority'),
        ('hazard', 'Hazardous Conditions'),
        ('intensity', 'Work Intensity'),
        ('night', 'Night Work'),
        ('personal', 'Personal Allowance'),
        ('qualification', 'Qualification'),
        ('other', 'Other'),
    ], string='Category', required=True, default='other')
    
    is_taxable = fields.Boolean(string='Taxable (PDFO)', default=True)
    is_esv_base = fields.Boolean(string='ESV Base', default=True)
    default_percent = fields.Float(string='Default Percent')
    default_amount = fields.Float(string='Default Amount')
    
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _unique_code = models.Constraint(
        'unique(code)',
        'Allowance type code must be unique!',
    )
