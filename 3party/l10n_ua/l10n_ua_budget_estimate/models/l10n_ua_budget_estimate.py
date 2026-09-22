from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


FUND_SELECTION = [
    ('general', 'Загальний фонд'),
    ('special', 'Спеціальний фонд'),
    ('both', 'Загальний + Спеціальний'),
]

STATE_SELECTION = [
    ('draft', 'Чернетка'),
    ('submitted', 'Подано на затвердження'),
    ('approved', 'Затверджено'),
    ('executed', 'Виконується'),
    ('closed', 'Закрито'),
    ('cancelled', 'Скасовано'),
]


class L10nUaBudgetEstimate(models.Model):
    """Кошторис бюджетної установи.

    Документ зі складом видатків на бюджетний рік, розбитий по періодах і фондах.
    Регулюється Наказом Мінфіну № 44 від 28.01.2002 «Про порядок складання,
    розгляду, затвердження та основні вимоги до виконання кошторисів».
    """
    _name = 'l10n_ua.budget.estimate'
    _description = 'Кошторис бюджетної установи'
    _order = 'year desc, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Номер',
        required=True, copy=False, readonly=False, default='Новий',
        tracking=True)
    title = fields.Char(
        string='Назва кошторису',
        tracking=True,
        help='Описова назва — наприклад «Кошторис ЗДО № 12 на 2025 рік».')
    state = fields.Selection(
        STATE_SELECTION, string='Стан',
        default='draft', required=True, tracking=True, copy=False)
    year = fields.Integer(
        string='Бюджетний рік',
        required=True, tracking=True, default=lambda self: fields.Date.today().year)
    fund_type = fields.Selection(
        FUND_SELECTION, string='Фонд',
        default='both', required=True, tracking=True,
        help='Який фонд покриває цей кошторис.')
    company_id = fields.Many2one(
        'res.company', string='Установа', required=True,
        default=lambda self: self.env.company, tracking=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True, readonly=True)
    kpkvk_id = fields.Many2one(
        'l10n_ua.kpkvk', string='КПКВК', tracking=True,
        help='Програмна класифікація: пропонується для кожного рядка за замовчуванням.')
    kfk_id = fields.Many2one(
        'l10n_ua.kfk', string='КФК',
        related='kpkvk_id.kfk_id', store=True, readonly=True)
    kvkv_id = fields.Many2one(
        'l10n_ua.kvkv', string='ГРБК (КВКВ)',
        related='kpkvk_id.kvkv_id', store=True, readonly=True)
    date_from = fields.Date(
        string='Період з',
        compute='_compute_period_dates', store=True, readonly=False, tracking=True)
    date_to = fields.Date(
        string='Період до',
        compute='_compute_period_dates', store=True, readonly=False, tracking=True)

    approval_date = fields.Date(string='Дата затвердження', tracking=True, copy=False)
    approved_by_id = fields.Many2one(
        'res.users', string='Затвердив',
        tracking=True, copy=False, readonly=True)
    notes = fields.Html(string='Примітки')

    line_ids = fields.One2many(
        'l10n_ua.budget.estimate.line', 'estimate_id',
        string='Рядки кошторису', copy=True)

    # Aggregates
    total_planned = fields.Monetary(
        string='Усього план', currency_field='currency_id',
        compute='_compute_totals', store=True)
    total_general = fields.Monetary(
        string='Загальний фонд', currency_field='currency_id',
        compute='_compute_totals', store=True)
    total_special = fields.Monetary(
        string='Спеціальний фонд', currency_field='currency_id',
        compute='_compute_totals', store=True)
    total_actual = fields.Monetary(
        string='Касове виконання', currency_field='currency_id',
        compute='_compute_totals', store=True)
    execution_percent = fields.Float(
        string='% виконання', compute='_compute_totals', store=True,
        help='Відношення касового виконання до затвердженого плану.')

    parent_estimate_id = fields.Many2one(
        'l10n_ua.budget.estimate', string='Попередня версія', copy=False,
        help='Якщо це довідка про зміни — посилання на затверджений кошторис, який ця версія змінює.')
    is_amendment = fields.Boolean(
        string='Довідка про зміни',
        compute='_compute_is_amendment', store=True)

    # Constraints
    _name_company_year_uniq = models.Constraint(
        'unique(name, company_id, year)',
        'Номер кошторису має бути унікальним у межах установи та року.',
    )

    @api.depends('year')
    def _compute_period_dates(self):
        for rec in self:
            if rec.year:
                rec.date_from = fields.Date.from_string(f'{rec.year}-01-01')
                rec.date_to = fields.Date.from_string(f'{rec.year}-12-31')

    @api.depends('parent_estimate_id')
    def _compute_is_amendment(self):
        for rec in self:
            rec.is_amendment = bool(rec.parent_estimate_id)

    @api.depends('line_ids.amount_planned', 'line_ids.fund_type',
                  'line_ids.amount_actual')
    def _compute_totals(self):
        for rec in self:
            general = sum(l.amount_planned for l in rec.line_ids
                          if l.fund_type == 'general')
            special = sum(l.amount_planned for l in rec.line_ids
                          if l.fund_type == 'special')
            actual = sum(l.amount_actual for l in rec.line_ids)
            planned = general + special
            rec.total_general = general
            rec.total_special = special
            rec.total_planned = planned
            rec.total_actual = actual
            rec.execution_percent = (actual / planned * 100.0) if planned else 0.0

    @api.constrains('year')
    def _check_year(self):
        for rec in self:
            if rec.year and (rec.year < 1990 or rec.year > 2100):
                raise ValidationError(_('Некоректний бюджетний рік: %s') % rec.year)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Новий') == 'Новий':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'l10n_ua.budget.estimate') or 'Новий'
        return super().create(vals_list)

    # === State machine ===

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Можна подавати лише чернетки.'))
            if not rec.line_ids:
                raise UserError(_('Не можна подати порожній кошторис — додайте хоча б один рядок.'))
            rec.state = 'submitted'

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Затверджувати можна лише поданий кошторис.'))
            rec.write({
                'state': 'approved',
                'approval_date': fields.Date.context_today(rec),
                'approved_by_id': self.env.uid,
            })

    def action_execute(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Запускати виконання можна лише затвердженого кошторису.'))
            rec.state = 'executed'

    def action_close(self):
        for rec in self:
            if rec.state not in ('approved', 'executed'):
                raise UserError(_('Закривати можна лише затверджений або виконуваний кошторис.'))
            rec.state = 'closed'

    def action_cancel(self):
        for rec in self:
            if rec.state in ('closed',):
                raise UserError(_('Закритий кошторис не можна скасувати — створіть довідку про зміни.'))
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('submitted', 'cancelled'):
                raise UserError(_('У чернетку можна повернути лише поданий або скасований кошторис.'))
            rec.state = 'draft'

    def action_recompute_actuals(self):
        """Manually trigger plan vs actual recalculation across all lines."""
        for rec in self:
            rec.line_ids._compute_amount_actual()
