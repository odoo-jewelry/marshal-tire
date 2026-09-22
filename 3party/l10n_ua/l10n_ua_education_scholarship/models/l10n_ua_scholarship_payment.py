from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


STATE_SELECTION = [
    ('draft', 'Чернетка'),
    ('approved', 'Затверджено'),
    ('paid', 'Виплачено'),
    ('cancelled', 'Скасовано'),
]


class L10nUaScholarshipPayment(models.Model):
    """Відомість виплати стипендій за звітний місяць.

    Один документ → багато рядків (по членах контингенту). При проведенні
    (`action_pay`) можна генерувати account.move з аналітикою КЕКВ/Фонд/КПКВК
    для подальшого контролю ліміту через l10n_ua_budget_treasury.
    """
    _name = 'l10n_ua.scholarship.payment'
    _description = 'Відомість виплати стипендії'
    _order = 'period_year desc, period_month desc, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Номер', required=True, copy=False, default='Нова',
                       tracking=True)
    state = fields.Selection(STATE_SELECTION, default='draft', required=True,
                              tracking=True, copy=False)
    company_id = fields.Many2one('res.company', required=True,
                                  default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id',
                                    store=True, readonly=True)
    scholarship_type_id = fields.Many2one(
        'l10n_ua.scholarship.type', string='Тип стипендії', required=True,
        tracking=True)
    period_year = fields.Integer(string='Рік', required=True, tracking=True,
                                  default=lambda self: fields.Date.today().year)
    period_month = fields.Selection([
        ('1', 'Січень'), ('2', 'Лютий'), ('3', 'Березень'),
        ('4', 'Квітень'), ('5', 'Травень'), ('6', 'Червень'),
        ('7', 'Липень'), ('8', 'Серпень'), ('9', 'Вересень'),
        ('10', 'Жовтень'), ('11', 'Листопад'), ('12', 'Грудень'),
    ], string='Місяць', required=True, tracking=True,
       default=lambda self: str(fields.Date.today().month))
    payment_date = fields.Date(string='Дата виплати', tracking=True,
                                default=fields.Date.context_today)
    academic_year_id = fields.Many2one(
        'l10n_ua.education.academic.year', string='Навчальний рік')
    kekv_id = fields.Many2one(
        'l10n_ua.kekv', string='КЕКВ',
        domain="[('child_ids', '=', False)]",
        compute='_compute_default_kekv', store=True, readonly=False)
    fund_type = fields.Selection([
        ('general', 'Загальний фонд'),
        ('special', 'Спеціальний фонд'),
    ], string='Фонд', required=True, default='general', tracking=True)
    kpkvk_id = fields.Many2one('l10n_ua.kpkvk', string='КПКВК')
    notes = fields.Html(string='Примітки')
    line_ids = fields.One2many(
        'l10n_ua.scholarship.payment.line', 'payment_id',
        string='Рядки виплати', copy=True)
    total_amount = fields.Monetary(string='Усього (брутто)', currency_field='currency_id',
                                    compute='_compute_total', store=True)
    total_pdfo = fields.Monetary(string='Усього ПДФО', currency_field='currency_id',
                                  compute='_compute_total', store=True)
    total_vz = fields.Monetary(string='Усього військового збору', currency_field='currency_id',
                                compute='_compute_total', store=True)
    total_net = fields.Monetary(string='Усього (нетто, до виплати)', currency_field='currency_id',
                                 compute='_compute_total', store=True)
    line_count = fields.Integer(compute='_compute_total', store=True)

    # Tax rates — за чинним законодавством (Податковий кодекс)
    pdfo_rate = fields.Float(string='Ставка ПДФО, %', default=18.0,
                              help='Ставка податку на доходи фізосіб (стандартно 18%).')
    vz_rate = fields.Float(string='Ставка військового збору, %', default=5.0,
                            help='Ставка військового збору (з 01.12.2024 — 5%).')

    # Accounts for generated journal entry (optional)
    journal_id = fields.Many2one('account.journal', string='Журнал нарахування',
                                   help='Якщо вказано — при action_pay створюється проводка нарахування.')
    account_expense_id = fields.Many2one(
        'account.account', string='Рахунок витрат',
        help='Зазвичай 8011 (для нерозпорядників) або 8111 (для розпорядників).')
    account_payable_id = fields.Many2one(
        'account.account', string='Рахунок розрахунків зі студентами',
        help='Зазвичай 6514 (депоновані) або інший liability_current.')
    account_pdfo_id = fields.Many2one(
        'account.account', string='Рахунок ПДФО (до перерахування в бюджет)')
    account_vz_id = fields.Many2one(
        'account.account', string='Рахунок військового збору')
    account_move_id = fields.Many2one(
        'account.move', string='Згенерована проводка', readonly=True, copy=False,
        help='Документ нарахування стипендії — створюється при дії «Виплатити».')

    @api.depends('scholarship_type_id')
    def _compute_default_kekv(self):
        for rec in self:
            if rec.scholarship_type_id and not rec.kekv_id:
                rec.kekv_id = rec.scholarship_type_id.default_kekv_id

    @api.depends('line_ids.amount', 'line_ids.amount_pdfo', 'line_ids.amount_vz', 'line_ids.amount_net')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))
            rec.total_pdfo = sum(rec.line_ids.mapped('amount_pdfo'))
            rec.total_vz = sum(rec.line_ids.mapped('amount_vz'))
            rec.total_net = sum(rec.line_ids.mapped('amount_net'))
            rec.line_count = len(rec.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Нова') == 'Нова':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'l10n_ua.scholarship.payment') or 'Нова'
        return super().create(vals_list)

    # === State machine ===

    def action_approve(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Затверджувати можна лише чернетку.'))
            if not rec.line_ids:
                raise UserError(_('Не можна затвердити порожню відомість.'))
            rec.state = 'approved'

    def action_pay(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Виплачувати можна лише затверджену відомість.'))
            if rec.journal_id:
                rec._create_account_move()
            rec.state = 'paid'

    def _create_account_move(self):
        """Generate accrual journal entry: Dr expense / Cr payable + tax payables."""
        self.ensure_one()
        if not (self.account_expense_id and self.account_payable_id):
            raise UserError(_(
                'Для нарахування потрібно заповнити журнал, рахунок витрат '
                'і рахунок розрахунків зі студентами на відомості.'))

        AccountMove = self.env['account.move']
        # Aggregate per fund_type for cleaner posting (one move with grouped lines)
        gross = sum(self.line_ids.mapped('amount'))
        pdfo = sum(self.line_ids.mapped('amount_pdfo'))
        vz = sum(self.line_ids.mapped('amount_vz'))
        net = gross - pdfo - vz
        if gross <= 0:
            raise UserError(_('Сума брутто = 0, нічого нараховувати.'))

        date_str = self.payment_date or fields.Date.context_today(self)
        analytic = {
            'ua_kekv_id': self.kekv_id.id,
            'ua_fund_type': self.fund_type,
            'ua_kpkvk_id': self.kpkvk_id.id if self.kpkvk_id else False,
        }
        lines = [
            (0, 0, dict(
                analytic,
                account_id=self.account_expense_id.id,
                name=_('Нарахування стипендій %s', self.name),
                debit=gross, credit=0,
            )),
            (0, 0, dict(
                analytic,
                account_id=self.account_payable_id.id,
                name=_('До виплати студентам %s', self.name),
                debit=0, credit=net,
            )),
        ]
        if pdfo > 0 and self.account_pdfo_id:
            lines.append((0, 0, dict(
                analytic,
                account_id=self.account_pdfo_id.id,
                name=_('ПДФО з стипендій %s', self.name),
                debit=0, credit=pdfo,
            )))
        if vz > 0 and self.account_vz_id:
            lines.append((0, 0, dict(
                analytic,
                account_id=self.account_vz_id.id,
                name=_('Військовий збір з стипендій %s', self.name),
                debit=0, credit=vz,
            )))
        move = AccountMove.create({
            'move_type': 'entry',
            'journal_id': self.journal_id.id,
            'date': date_str,
            'company_id': self.company_id.id,
            'ref': _('Стипендії %s', self.name),
            'line_ids': lines,
        })
        move.action_post()
        self.account_move_id = move.id
        return move

    def action_cancel(self):
        for rec in self:
            if rec.state == 'paid':
                raise UserError(_('Виплачену відомість не можна скасувати — лише сторнувати окремою операцією.'))
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('approved', 'cancelled'):
                raise UserError(_('Повернути в чернетку можна лише затверджену або скасовану відомість.'))
            rec.state = 'draft'


class L10nUaScholarshipPaymentLine(models.Model):
    _name = 'l10n_ua.scholarship.payment.line'
    _description = 'Рядок виплати стипендії'
    _order = 'payment_id, member_id'

    payment_id = fields.Many2one('l10n_ua.scholarship.payment', required=True,
                                   ondelete='cascade', index=True)
    company_id = fields.Many2one(related='payment_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='payment_id.currency_id', store=True, readonly=True)
    state = fields.Selection(related='payment_id.state', store=True, readonly=True)
    member_id = fields.Many2one(
        'l10n_ua.education.contingent.member', string='Учень / Студент',
        required=True, ondelete='restrict', index=True,
        domain="[('state', 'in', ('enrolled', 'studying'))]")
    partner_id = fields.Many2one(related='member_id.partner_id', store=True, readonly=True)
    group_id = fields.Many2one(related='member_id.group_id', store=True, readonly=True)
    amount = fields.Monetary(string='Сума (брутто)', currency_field='currency_id',
                              compute='_compute_amount', store=True, readonly=False,
                              required=True, precompute=True)
    amount_pdfo = fields.Monetary(string='ПДФО', currency_field='currency_id',
                                    compute='_compute_taxes', store=True,
                                    help='Податок на доходи фізосіб. Розраховується, '
                                         'якщо тип стипендії оподатковується.')
    amount_vz = fields.Monetary(string='Військовий збір', currency_field='currency_id',
                                  compute='_compute_taxes', store=True)
    amount_net = fields.Monetary(string='До виплати (нетто)', currency_field='currency_id',
                                   compute='_compute_taxes', store=True)
    is_taxable = fields.Boolean(
        related='payment_id.scholarship_type_id.is_taxable_pdfo',
        store=True, readonly=True)
    note = fields.Char(string='Примітка')

    @api.depends(
        'payment_id.scholarship_type_id',
        'payment_id.period_year',
        'payment_id.period_month',
        'payment_id.company_id',
    )
    def _compute_amount(self):
        for line in self:
            if not line.amount and line.payment_id.scholarship_type_id:
                payment = line.payment_id
                effective_date = None
                if payment.period_year and payment.period_month:
                    effective_date = date(
                        payment.period_year, int(payment.period_month), 1)
                line.amount = payment.scholarship_type_id._get_monthly_amount(
                    effective_date, payment.company_id)

    @api.depends('amount', 'is_taxable', 'payment_id.pdfo_rate', 'payment_id.vz_rate')
    def _compute_taxes(self):
        for line in self:
            if line.is_taxable and line.amount > 0:
                pdfo_rate = (line.payment_id.pdfo_rate or 0) / 100.0
                vz_rate = (line.payment_id.vz_rate or 0) / 100.0
                line.amount_pdfo = round(line.amount * pdfo_rate, 2)
                line.amount_vz = round(line.amount * vz_rate, 2)
            else:
                line.amount_pdfo = 0.0
                line.amount_vz = 0.0
            line.amount_net = line.amount - line.amount_pdfo - line.amount_vz

    @api.constrains('amount')
    def _check_non_negative(self):
        for line in self:
            if line.amount < 0:
                raise ValidationError(_('Сума стипендії не може бути від\'ємною.'))

    _member_payment_uniq = models.Constraint(
        'unique(payment_id, member_id)',
        'Один член контингенту не може мати кілька рядків в одній відомості!',
    )
