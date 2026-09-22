from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nUaAccountCard(models.Model):
    _name = 'l10n_ua.account.card'
    _description = 'Account Card (Картка рахунку)'
    _order = 'period_start desc, account_id'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    account_id = fields.Many2one(
        'account.account',
        string='Account',
        required=True,
    )
    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
    )

    # --- Опційний фільтр за субконто ---
    partner_id = fields.Many2one(
        'res.partner',
        string='Partner (subconto)',
        help='Фільтрувати рух рахунку за конкретним контрагентом (субконто).',
    )
    subconto_type_id = fields.Many2one(
        'l10n_ua.subconto.type',
        string='Subconto Type',
        help='Тип субконто для фільтра (товар, підрозділ тощо).',
    )
    subconto_res_id = fields.Integer(
        string='Subconto Record ID',
        help='ID запису субконто обраного типу.',
    )

    line_ids = fields.One2many(
        'l10n_ua.account.card.line',
        'card_id',
        string='Lines',
    )
    opening_balance = fields.Monetary(
        string='Opening Balance',
        readonly=True,
        currency_field='currency_id',
        help='Сальдо рахунку на початок періоду (сума руху до period_start).',
    )
    total_debit = fields.Monetary(
        string='Total Debit',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_credit = fields.Monetary(
        string='Total Credit',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    closing_balance = fields.Monetary(
        string='Closing Balance',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('confirmed', 'Confirmed')],
        string='State',
        default='draft',
    )

    @api.depends('account_id', 'period_start', 'period_end')
    def _compute_name(self):
        for record in self:
            if record.account_id and record.period_start:
                record.name = '%s (%s - %s)' % (
                    record.account_id.code or record.account_id.name,
                    record.period_start, record.period_end)
            else:
                record.name = _('New')

    @api.depends('line_ids.debit', 'line_ids.credit', 'opening_balance')
    def _compute_totals(self):
        for record in self:
            record.total_debit = sum(record.line_ids.mapped('debit'))
            record.total_credit = sum(record.line_ids.mapped('credit'))
            record.closing_balance = (
                record.opening_balance + record.total_debit - record.total_credit)

    def action_compute(self):
        """Побудувати картку рахунку: хронологічний рух із наростаючим залишком.

        Читає posted-рядки ``account.move.line`` обраного рахунку за період
        (опційно звужені за партнером/субконто), рахує початкове сальдо (рух
        до періоду) і наростаючий залишок після кожної проводки. Кореспондуючий
        рахунок — з протилежного боку тієї ж проводки.
        """
        self.ensure_one()
        if not self.period_start or not self.period_end:
            raise UserError(_('Вкажіть початок і кінець періоду.'))
        if self.period_end < self.period_start:
            raise UserError(_('Кінець періоду не може бути раніше за початок.'))

        self.line_ids.unlink()

        AML = self.env['account.move.line']
        domain = [
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', self.account_id.id),
        ]
        if self.partner_id:
            domain.append(('partner_id', '=', self.partner_id.id))
        if self.subconto_type_id and self.subconto_res_id:
            sub_lines = self.env['l10n_ua.move.line.subconto'].search([
                ('subconto_type_id', '=', self.subconto_type_id.id),
                ('res_id', '=', self.subconto_res_id),
            ]).move_line_id
            domain.append(('id', 'in', sub_lines.ids))

        # Початкове сальдо: чистий рух до початку періоду.
        opening_rows = AML._read_group(
            domain + [('date', '<', self.period_start)], [], ['balance:sum'])
        opening = (opening_rows[0][0] or 0.0) if opening_rows else 0.0
        self.opening_balance = opening

        amls = AML.search(
            domain + [
                ('date', '>=', self.period_start),
                ('date', '<=', self.period_end),
            ],
            order='date, move_id, id')

        running = opening
        lines = []
        for aml in amls:
            running += aml.balance
            opposite = aml.move_id.line_ids.filtered(
                lambda l: l.id != aml.id
                and (l.credit > 0 if aml.debit > 0 else l.debit > 0))
            lines.append((0, 0, {
                'date': aml.date,
                'move_id': aml.move_id.id,
                'corr_account_id': opposite.account_id[:1].id or False,
                'partner_id': aml.partner_id.id or False,
                'description': aml.name or aml.move_id.ref or aml.move_id.name or '',
                'debit': aml.debit,
                'credit': aml.credit,
                'running_balance': running,
            }))
        self.line_ids = lines
        return True

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})


class L10nUaAccountCardLine(models.Model):
    _name = 'l10n_ua.account.card.line'
    _description = 'Account Card Line'
    _order = 'date, id'

    card_id = fields.Many2one(
        'l10n_ua.account.card',
        string='Account Card',
        required=True,
        ondelete='cascade',
    )
    date = fields.Date(string='Date')
    move_id = fields.Many2one('account.move', string='Journal Entry')
    corr_account_id = fields.Many2one(
        'account.account',
        string='Corresponding Account',
    )
    partner_id = fields.Many2one('res.partner', string='Partner')
    description = fields.Char(string='Description')
    debit = fields.Monetary(string='Debit', currency_field='currency_id')
    credit = fields.Monetary(string='Credit', currency_field='currency_id')
    running_balance = fields.Monetary(
        string='Balance',
        currency_field='currency_id',
        help='Наростаючий залишок після цієї проводки.',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='card_id.currency_id',
    )
