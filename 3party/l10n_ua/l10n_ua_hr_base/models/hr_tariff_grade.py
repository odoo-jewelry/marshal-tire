from odoo import models, fields


class HrTariffGrade(models.Model):
    _name = 'hr.tariff.grade'
    _description = 'Tariff Grade'
    _order = 'grade'

    name = fields.Char(string='Name', required=True)
    grade = fields.Integer(string='Grade', required=True)
    coefficient = fields.Float(string='Coefficient', digits=(16, 4), default=1.0)
    min_salary = fields.Monetary( string='Monthly Salary', help='Місячний оклад для службовців (НЕ погодинна ставка)', currency_field='currency_id',)
    hourly_rate = fields.Monetary( string='Hourly Rate', help='Базова погодинна ставка для робочих спеціальностей (грн/год)', currency_field='currency_id',)
    currency_id = fields.Many2one('res.currency', string='Currency',
                                   default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(string='Active', default=True)

    _grade_uniq = models.Constraint(
        'unique(grade)',
        'Tariff grade must be unique!',
    )
