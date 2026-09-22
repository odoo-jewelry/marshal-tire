from odoo import models, fields, api, _


class HrPayslipRetro(models.Model):
    """Аудит ретро-перерахунку зарплати за закритий період (#151).

    Один запис = одне перенесення різниці (дельти) з перерахованого минулого
    листка у поточний чернетковий. Зберігає було/стало/дельту та посилання на
    створений рядок нарахування, що дає простежуваність і робить повторний
    перерахунок ідемпотентним (старий рядок видаляється й створюється новий).
    """
    _name = 'hr.payslip.retro'
    _description = 'Payroll Retro Recalculation'
    _order = 'create_date desc'

    source_payslip_id = fields.Many2one(
        'hr.payslip', string='Source Payslip', required=True,
        ondelete='cascade',
        help='Закритий листок минулого періоду, що перераховувався.')
    target_payslip_id = fields.Many2one(
        'hr.payslip', string='Target Payslip', required=True,
        ondelete='cascade',
        help='Поточний листок, у який перенесено різницю.')
    accrual_line_id = fields.Many2one(
        'hr.payslip.accrual', string='Retro Line', ondelete='set null',
        help='Рядок нарахування «Перерахунок» у поточному листку.')

    employee_id = fields.Many2one(
        'hr.employee', related='source_payslip_id.employee_id', store=True)
    source_date_to = fields.Date(
        related='source_payslip_id.date_to', store=True, string='Period')

    old_gross = fields.Monetary(string='Old Gross', currency_field='currency_id')
    new_gross = fields.Monetary(string='New Gross', currency_field='currency_id')
    gross_delta = fields.Monetary(string='Delta', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='source_payslip_id.currency_id')
    company_id = fields.Many2one(
        'res.company', related='source_payslip_id.company_id', store=True)

    def _sync_line_amount(self):
        """Оновити суму рядка нарахування відповідно до дельти."""
        for rec in self:
            if rec.accrual_line_id:
                rec.accrual_line_id.amount = rec.gross_delta
