from odoo import models, fields


class HrEducationLevel(models.Model):
    _name = 'hr.education.level'
    _description = 'Education Level'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _code_uniq = models.Constraint(
        'unique(code)',
        'Education level code must be unique!',
    )
