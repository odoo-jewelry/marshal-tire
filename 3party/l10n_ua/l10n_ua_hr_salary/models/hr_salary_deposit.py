from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class HrSalaryDeposit(models.Model):
    """Депонент — нарахована, але невиплачена у строк заробітна плата (#155).

    Фіксує суму до виплати по працівнику, веде облік часткових виплат і
    залишку (residual), доки депонент не буде погашено повністю.
    """
    _name = 'hr.salary.deposit'
    _description = 'Salary Deposit (депонент)'
    _inherit = ['mail.thread']
    _order = 'deposit_date desc, id desc'

    name = fields.Char(string='Reference', required=True, default='New', copy=False)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, tracking=True)
    source_payslip_id = fields.Many2one(
        'hr.payslip', string='Source Payslip', tracking=True,
        help='Розрахунковий листок, зарплату за яким депоновано.')
    deposit_date = fields.Date(
        string='Deposit Date', required=True,
        default=fields.Date.context_today, tracking=True)
    amount = fields.Monetary(
        string='Amount', required=True, tracking=True,
        currency_field='currency_id',
        help='Нарахована сума до виплати, що депонується.')

    payment_ids = fields.One2many(
        'hr.salary.deposit.payment', 'deposit_id', string='Payments')
    paid_amount = fields.Monetary(
        string='Paid', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    residual = fields.Monetary(
        string='Residual', compute='_compute_amounts', store=True,
        currency_field='currency_id')
    state = fields.Selection([
        ('deposited', 'Deposited'),
        ('partial', 'Partially Paid'),
        ('paid', 'Paid'),
    ], string='Status', compute='_compute_amounts', store=True, tracking=True)

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company,
        required=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    note = fields.Text(string='Note')

    @api.depends('amount', 'payment_ids.amount')
    def _compute_amounts(self):
        for rec in self:
            paid = sum(rec.payment_ids.mapped('amount'))
            rec.paid_amount = paid
            rec.residual = rec.amount - paid
            if paid <= 0:
                rec.state = 'deposited'
            elif rec.residual > 0:
                rec.state = 'partial'
            else:
                rec.state = 'paid'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'hr.salary.deposit') or 'New'
        return super().create(vals_list)

    def action_pay_full(self):
        """Погасити залишок депонента однією виплатою."""
        for rec in self:
            if rec.residual <= 0:
                continue
            self.env['hr.salary.deposit.payment'].create({
                'deposit_id': rec.id,
                'amount': rec.residual,
            })
        return True

    _check_amount_positive = models.Constraint(
        'CHECK(amount > 0)',
        'Сума депонента має бути додатною!',
    )


class HrSalaryDepositPayment(models.Model):
    """Виплата (погашення) депонованої суми."""
    _name = 'hr.salary.deposit.payment'
    _description = 'Salary Deposit Payment'
    _order = 'payment_date desc, id desc'

    deposit_id = fields.Many2one(
        'hr.salary.deposit', string='Deposit', required=True, ondelete='cascade')
    payment_date = fields.Date(
        string='Payment Date', required=True,
        default=fields.Date.context_today)
    amount = fields.Monetary(
        string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', related='deposit_id.currency_id')
    note = fields.Char(string='Note')

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Сума виплати має бути додатною.'))
            other = sum(
                (rec.deposit_id.payment_ids - rec).mapped('amount'))
            if other + rec.amount > rec.deposit_id.amount + 0.01:
                raise ValidationError(_(
                    'Сума виплат (%(paid).2f) перевищує депоновану суму '
                    '(%(total).2f).') % {
                        'paid': other + rec.amount,
                        'total': rec.deposit_id.amount})


class HrEmployeeDeposit(models.Model):
    _inherit = 'hr.employee'

    salary_deposit_residual = fields.Monetary(
        string='Deposited (unpaid) Salary',
        compute='_compute_salary_deposit_residual',
        currency_field='currency_id')

    def _compute_salary_deposit_residual(self):
        Deposit = self.env['hr.salary.deposit']
        data = Deposit._read_group(
            [('employee_id', 'in', self.ids), ('state', '!=', 'paid')],
            ['employee_id'], ['residual:sum'])
        mapped = {emp.id: total for emp, total in data}
        for emp in self:
            emp.salary_deposit_residual = mapped.get(emp.id, 0.0)


class HrPayslipDeposit(models.Model):
    _inherit = 'hr.payslip'

    deposit_ids = fields.One2many(
        'hr.salary.deposit', 'source_payslip_id', string='Deposits')

    def action_deposit_unpaid(self):
        """Депонувати невиплачену суму листка (net_salary) — #155."""
        Deposit = self.env['hr.salary.deposit']
        for slip in self:
            if slip.state != 'done':
                raise UserError(_(
                    'Депонувати можна лише закритий (Done) листок. '
                    'Листок «%s» у стані «%s».') % (slip.name, slip.state))
            if slip.deposit_ids:
                raise UserError(_(
                    'Для листка «%s» депонент уже створено.') % slip.name)
            if slip.net_salary <= 0:
                raise UserError(_(
                    'Немає суми до виплати для депонування (net = %.2f).'
                ) % slip.net_salary)
            Deposit.create({
                'employee_id': slip.employee_id.id,
                'source_payslip_id': slip.id,
                'amount': slip.net_salary,
                'company_id': slip.company_id.id,
                'note': _('Депоновано за листком %s (%s)') % (
                    slip.name, slip.date_to.strftime('%m.%Y')),
            })
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': _('Депонування'),
                       'message': _('Депонент створено.'),
                       'type': 'success', 'sticky': False},
        }
