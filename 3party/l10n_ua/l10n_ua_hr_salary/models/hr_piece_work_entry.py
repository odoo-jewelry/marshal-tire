from odoo import models, fields, api


class HrPieceWorkEntry(models.Model):
    """Наряд відрядної оплати (виробіток × розцінка).

    Для працівників на відрядній формі оплати праці: обсяг виконаної роботи
    за розцінкою. Суми за період (місяць нарахування) агрегуються в
    нарахування «Відрядна оплата» під час розрахунку зарплати.
    """
    _name = 'hr.piece.work.entry'
    _description = 'Наряд відрядної оплати'
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Операція / наряд', required=True,
        help='Опис виконаної роботи (операція, наряд).')
    employee_id = fields.Many2one(
        'hr.employee', string='Працівник', required=True, index=True)
    date = fields.Date(
        string='Дата', required=True, index=True,
        default=fields.Date.context_today,
        help='Дата виконання роботи. Визначає місяць нарахування.')
    quantity = fields.Float(string='Обсяг (виробіток)', required=True, default=0.0)
    unit_rate = fields.Float(string='Розцінка за одиницю', required=True, default=0.0)
    amount = fields.Monetary(
        string='Сума', compute='_compute_amount', store=True,
        currency_field='currency_id')
    company_id = fields.Many2one(
        'res.company', string='Компанія', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    _quantity_positive = models.Constraint(
        'CHECK(quantity >= 0)',
        'Обсяг виробітку не може бути відʼємним.')
    _rate_positive = models.Constraint(
        'CHECK(unit_rate >= 0)',
        'Розцінка не може бути відʼємною.')

    @api.depends('quantity', 'unit_rate')
    def _compute_amount(self):
        for rec in self:
            rec.amount = rec.quantity * rec.unit_rate
