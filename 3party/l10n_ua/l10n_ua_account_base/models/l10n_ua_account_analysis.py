from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nUaAccountAnalysis(models.Model):
    _name = 'l10n_ua.account.analysis'
    _description = 'Account Analysis (Аналіз рахунку)'
    _order = 'period_start desc, account_id'

    name = fields.Char(compute='_compute_name', store=True)
    account_id = fields.Many2one(
        'account.account', string='Account', required=True)
    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')

    line_ids = fields.One2many(
        'l10n_ua.account.analysis.line', 'analysis_id', string='Lines')
    opening_balance = fields.Monetary(
        string='Opening Balance', readonly=True, currency_field='currency_id',
        help='Сальдо рахунку на початок періоду.')
    total_debit = fields.Monetary(
        compute='_compute_totals', store=True, currency_field='currency_id')
    total_credit = fields.Monetary(
        compute='_compute_totals', store=True, currency_field='currency_id')
    closing_balance = fields.Monetary(
        compute='_compute_totals', store=True, currency_field='currency_id')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('confirmed', 'Confirmed')],
        string='State', default='draft')

    @api.depends('account_id', 'period_start', 'period_end')
    def _compute_name(self):
        for rec in self:
            if rec.account_id and rec.period_start:
                rec.name = '%s (%s - %s)' % (
                    rec.account_id.code or rec.account_id.name,
                    rec.period_start, rec.period_end)
            else:
                rec.name = _('New')

    @api.depends('line_ids.turnover_debit', 'line_ids.turnover_credit',
                 'opening_balance')
    def _compute_totals(self):
        for rec in self:
            rec.total_debit = sum(rec.line_ids.mapped('turnover_debit'))
            rec.total_credit = sum(rec.line_ids.mapped('turnover_credit'))
            rec.closing_balance = (
                rec.opening_balance + rec.total_debit - rec.total_credit)

    def action_compute(self):
        """Обороти рахунку за період у розрізі кореспондуючих рахунків.

        Для кожного рознесеного рядка обраного рахунку сума розподіляється
        на рахунки протилежного боку тієї ж проводки (пропорційно сумам),
        і групується за кореспондуючим рахунком.
        """
        self.ensure_one()
        if not self.period_start or not self.period_end:
            raise UserError(_('Вкажіть початок і кінець періоду.'))
        if self.period_end < self.period_start:
            raise UserError(_('Кінець періоду не може бути раніше за початок.'))

        self.line_ids.unlink()
        AML = self.env['account.move.line']
        base = [
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('account_id', '=', self.account_id.id),
        ]

        # Початкове сальдо: чистий рух до початку періоду.
        opening_rows = AML._read_group(
            base + [('date', '<', self.period_start)], [], ['balance:sum'])
        self.opening_balance = (opening_rows[0][0] or 0.0) if opening_rows else 0.0

        amls = AML.search(base + [
            ('date', '>=', self.period_start),
            ('date', '<=', self.period_end),
        ])

        # corr_account_id -> {'debit': .., 'credit': ..}
        data = {}

        def bucket(account):
            return data.setdefault(account.id, {
                'account': account, 'debit': 0.0, 'credit': 0.0})

        for line in amls:
            our_amount = line.debit or line.credit
            if not our_amount:
                continue
            our_is_debit = line.debit > 0
            # Протилежний бік проводки.
            opposite = line.move_id.line_ids.filtered(
                lambda l: l.id != line.id
                and (l.credit > 0 if our_is_debit else l.debit > 0))
            opp_field = 'credit' if our_is_debit else 'debit'
            opp_total = sum(opposite.mapped(opp_field))
            for opp in opposite:
                opp_amount = opp[opp_field]
                if opp_total:
                    share = our_amount * (opp_amount / opp_total)
                else:
                    share = our_amount / len(opposite)
                acc = bucket(opp.account_id)
                if our_is_debit:
                    acc['debit'] += share
                else:
                    acc['credit'] += share

        currency = self.company_id.currency_id
        lines = []
        for acc in data.values():
            if (currency.is_zero(acc['debit'])
                    and currency.is_zero(acc['credit'])):
                continue
            lines.append((0, 0, {
                'corr_account_id': acc['account'].id,
                'turnover_debit': acc['debit'],
                'turnover_credit': acc['credit'],
            }))
        self.line_ids = lines
        return True

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})


class L10nUaAccountAnalysisLine(models.Model):
    _name = 'l10n_ua.account.analysis.line'
    _description = 'Account Analysis Line'
    _order = 'corr_account_id'

    analysis_id = fields.Many2one(
        'l10n_ua.account.analysis', string='Analysis', required=True,
        ondelete='cascade')
    corr_account_id = fields.Many2one(
        'account.account', string='Corresponding Account', required=True)
    turnover_debit = fields.Monetary(
        string='Turnover Debit', currency_field='currency_id')
    turnover_credit = fields.Monetary(
        string='Turnover Credit', currency_field='currency_id')
    currency_id = fields.Many2one(related='analysis_id.currency_id')
