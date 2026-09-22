from odoo import models, fields


class HrMilitaryRank(models.Model):
    _name = 'hr.military.rank'
    _description = 'Military Rank'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code')
    category = fields.Selection([
        ('soldier', 'Soldier'),
        ('sergeant', 'Sergeant'),
        ('officer', 'Officer'),
        ('general', 'General'),
    ], string='Category', required=True, default='soldier')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _code_uniq = models.Constraint(
        'unique(code)',
        'Military rank code must be unique!',
    )
