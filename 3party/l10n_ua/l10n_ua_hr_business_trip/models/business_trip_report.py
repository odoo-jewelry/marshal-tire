"""Звіт про службове відрядження (#207)."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class BusinessTripReport(models.Model):
    _name = 'l10n_ua.business.trip.report'
    _description = 'Звіт про відрядження'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(
        string='Номер',
        required=True,
        copy=False,
        readonly=True,
        default='/',
    )
    date = fields.Date(
        string='Дата звіту',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Працівник',
        required=True,
        tracking=True,
    )
    order_id = fields.Many2one(
        'hr.order',
        string='Наказ на відрядження',
        domain="[('order_type', '=', 'business_trip'), "
               "('employee_id', '=', employee_id)]",
        tracking=True,
        help='Наказ про направлення у службове відрядження.',
    )
    destination = fields.Char(
        string='Місце відрядження',
        required=True,
    )
    purpose = fields.Char(
        string='Мета відрядження',
    )
    date_from = fields.Date(
        string='Дата вибуття',
        required=True,
        tracking=True,
    )
    date_to = fields.Date(
        string='Дата прибуття',
        required=True,
        tracking=True,
    )
    days = fields.Integer(
        string='Днів у відрядженні',
        compute='_compute_days',
        store=True,
        help='Календарні дні (включно з днями вибуття та прибуття).',
    )

    # --- Витрати ---
    daily_rate = fields.Monetary(
        string='Добові за день',
        currency_field='currency_id',
        default=lambda self: self.env.company.l10n_ua_business_trip_daily_rate,
    )
    daily_total = fields.Monetary(
        string='Добові разом',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    transport_amount = fields.Monetary(
        string='Проїзд',
        currency_field='currency_id',
    )
    accommodation_amount = fields.Monetary(
        string='Проживання',
        currency_field='currency_id',
    )
    other_amount = fields.Monetary(
        string='Інші витрати',
        currency_field='currency_id',
    )
    total_amount = fields.Monetary(
        string='Усього витрат',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    advance_report_id = fields.Many2one(
        'l10n_ua.advance.report',
        string='Авансовий звіт',
        readonly=True,
        copy=False,
        help='Авансовий звіт (підзвіт), сформований з цього звіту про відрядження.',
    )

    state = fields.Selection(
        selection=[
            ('draft', 'Чернетка'),
            ('confirmed', 'Затверджено'),
            ('cancelled', 'Скасовано'),
        ],
        string='Стан',
        default='draft',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Компанія',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
    )
    note = fields.Text(string='Примітки')

    # ------------------------------------------------------------------
    # Compute
    # ------------------------------------------------------------------

    @api.depends('date_from', 'date_to')
    def _compute_days(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to >= rec.date_from:
                rec.days = (rec.date_to - rec.date_from).days + 1
            else:
                rec.days = 0

    @api.depends('days', 'daily_rate', 'transport_amount',
                 'accommodation_amount', 'other_amount')
    def _compute_amounts(self):
        for rec in self:
            rec.daily_total = rec.days * rec.daily_rate
            rec.total_amount = (
                rec.daily_total + rec.transport_amount
                + rec.accommodation_amount + rec.other_amount
            )

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'l10n_ua.business.trip.report') or '/'
        return super().create(vals_list)

    @api.onchange('order_id')
    def _onchange_order_id(self):
        if self.order_id and self.order_id.employee_id:
            self.employee_id = self.order_id.employee_id

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_to < rec.date_from:
                raise UserError(_(
                    'Дата прибуття не може бути раніше дати вибуття.'))

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                continue
            rec.state = 'confirmed'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_draft(self):
        for rec in self:
            rec.state = 'draft'

    # ------------------------------------------------------------------
    # Advance report generation (підзвіт)
    # ------------------------------------------------------------------

    def _prepare_advance_report_lines(self):
        """Рядки авансового звіту з витрат відрядження (лише ненульові)."""
        self.ensure_one()
        specs = [
            (self.daily_total, 'meals', _('Добові (%s дн. × %s)') % (
                self.days, self.daily_rate)),
            (self.transport_amount, 'transport', _('Проїзд')),
            (self.accommodation_amount, 'accommodation', _('Проживання')),
            (self.other_amount, 'other', _('Інші витрати')),
        ]
        lines = []
        for amount, expense_type, description in specs:
            if self.currency_id.is_zero(amount):
                continue
            lines.append((0, 0, {
                'date': self.date_to or self.date,
                'description': description,
                'expense_type': expense_type,
                'amount': amount,
            }))
        return lines

    def action_create_advance_report(self):
        """Сформувати авансовий звіт (підзвіт) із звіту про відрядження."""
        self.ensure_one()
        if self.advance_report_id:
            raise UserError(_('Авансовий звіт уже сформовано.'))
        lines = self._prepare_advance_report_lines()
        if not lines:
            raise UserError(_('Немає витрат для авансового звіту.'))
        report = self.env['l10n_ua.advance.report'].create({
            'date': self.date,
            'employee_id': self.employee_id.id,
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'purpose': _('Відрядження: %s') % (self.destination or ''),
            'line_ids': lines,
        })
        self.advance_report_id = report
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_ua.advance.report',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_advance_report(self):
        self.ensure_one()
        if not self.advance_report_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_ua.advance.report',
            'res_id': self.advance_report_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_print(self):
        self.ensure_one()
        return self.env.ref(
            'l10n_ua_hr_business_trip.action_report_business_trip'
        ).report_action(self)
