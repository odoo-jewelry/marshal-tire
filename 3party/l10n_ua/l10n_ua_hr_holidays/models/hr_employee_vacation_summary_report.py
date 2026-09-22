from odoo import models, fields, api


class HrEmployeeVacationSummaryReport(models.Model):
    """Vacation Summary Report (Підсумок відпусток).

    Per-employee, per-leave-type vacation balance snapshot for a given year.
    Saved and reusable; can be regenerated and printed to PDF.
    """
    _name = 'hr.employee.vacation.summary.report'
    _description = 'Vacation Summary Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'report_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    report_date = fields.Date(
        string='As of Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help='The report shows, per employee and leave type, the vacation '
             'period this date falls into.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )
    balance_ids = fields.Many2many(
        'hr.vacation.balance',
        string='Vacation Balances',
    )
    employee_count = fields.Integer(
        string='Employees',
        compute='_compute_totals',
        store=True,
    )
    total_entitled = fields.Float(
        string='Entitled',
        compute='_compute_totals',
        store=True,
    )
    total_used = fields.Float(
        string='Used',
        compute='_compute_totals',
        store=True,
    )
    total_remaining = fields.Float(
        string='Remaining',
        compute='_compute_totals',
        store=True,
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('generated', 'Generated')],
        default='draft',
        tracking=True,
    )
    notes = fields.Text()

    @api.depends('report_date')
    def _compute_name(self):
        for rec in self:
            if rec.report_date:
                rec.name = 'Підсумок відпусток на %s' % (
                    rec.report_date.strftime('%d.%m.%Y'))
            else:
                rec.name = 'Підсумок відпусток'

    @api.depends('balance_ids', 'balance_ids.entitled_days',
                 'balance_ids.used_days', 'balance_ids.remaining_days')
    def _compute_totals(self):
        for rec in self:
            balances = rec.balance_ids
            rec.employee_count = len(balances.mapped('employee_id'))
            rec.total_entitled = sum(balances.mapped('entitled_days'))
            rec.total_used = sum(balances.mapped('used_days'))
            rec.total_remaining = sum(balances.mapped('remaining_days'))

    def action_generate(self):
        Balance = self.env['hr.vacation.balance']
        for rec in self:
            ref_date = rec.report_date or fields.Date.context_today(rec)
            # Make sure every employee/auto-calc leave type has the period the
            # selected date falls into. generate_balances backfills the whole
            # chain up to that date, so a missing period (including one past the
            # last existing period) is created and then picked up below.
            Balance.sudo().generate_balances(up_to_date=ref_date)
            # Select the period each employee/leave type is in on that date —
            # period_start <= date <= period_end — exactly like the Vacation
            # Balances (Залишки відпусток) report. remaining_days is the same
            # field, so the figures agree.
            balances = Balance.search(
                [
                    ('employee_id.company_id', '=', rec.company_id.id),
                    ('period_start', '<=', ref_date),
                    ('period_end', '>=', ref_date),
                ],
                order='employee_id, leave_type_id',
            )
            rec.write({
                'balance_ids': [(6, 0, balances.ids)],
                'state': 'generated',
            })
        return True

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_print(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_ua_hr_holidays.action_report_hr_employee_vacation_summary'
        ).report_action(self)
