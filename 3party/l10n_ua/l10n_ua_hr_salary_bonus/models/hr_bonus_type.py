from odoo import models, fields


class HrBonusType(models.Model):
    _name = 'hr.bonus.type'
    _description = 'Bonus Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        required=True,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    is_taxable_pdfo = fields.Boolean(
        string='Taxable (PDFO)',
        default=True,
        help='Include in personal income tax (PDFO) calculation',
    )
    is_military_tax = fields.Boolean(
        string='Military Tax',
        default=True,
        help='Include in military tax calculation',
    )
    is_esv_base = fields.Boolean(
        string='ESV Base',
        default=True,
        help='Include in unified social contribution (ESV) base',
    )
    d4_income_type = fields.Char(
        string='4DF Income Type',
        default='101',
        help='Income type code for 4DF tax report',
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    _code_uniq = models.Constraint(
        'UNIQUE(code, company_id)',
        'Bonus type code must be unique per company!',
    )
