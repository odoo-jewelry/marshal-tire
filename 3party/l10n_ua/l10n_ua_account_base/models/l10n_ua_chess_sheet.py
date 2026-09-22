from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nUaChessSheet(models.Model):
    _name = 'l10n_ua.chess.sheet'
    _description = 'Chess Sheet (Шахматка)'
    _order = 'period_start desc'

    name = fields.Char(compute='_compute_name', store=True)
    period_start = fields.Date(string='Period Start', required=True)
    period_end = fields.Date(string='Period End', required=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many(
        'l10n_ua.chess.sheet.line', 'chess_id', string='Cells')
    total_amount = fields.Monetary(
        compute='_compute_total', store=True, currency_field='currency_id',
        help='Загальний оборот (має дорівнювати сумі Дт = сумі Кт).')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('confirmed', 'Confirmed')],
        string='State', default='draft')

    @api.depends('period_start', 'period_end')
    def _compute_name(self):
        for rec in self:
            if rec.period_start:
                rec.name = _('Шахматка %s - %s') % (
                    rec.period_start, rec.period_end)
            else:
                rec.name = _('New')

    @api.depends('line_ids.amount')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('amount'))

    def action_compute(self):
        """Матриця оборотів: для кожної проводки суми розкладаються на пари
        (Дт-рахунок × Кт-рахунок) пропорційно, і агрегуються по кореспонденції."""
        self.ensure_one()
        if not self.period_start or not self.period_end:
            raise UserError(_('Вкажіть початок і кінець періоду.'))
        if self.period_end < self.period_start:
            raise UserError(_('Кінець періоду не може бути раніше за початок.'))

        self.line_ids.unlink()
        moves = self.env['account.move'].search([
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.period_start),
            ('date', '<=', self.period_end),
        ])

        # (debit_account_id, credit_account_id) -> amount
        cells = {}
        for move in moves:
            debits = move.line_ids.filtered(lambda l: l.debit > 0)
            credits = move.line_ids.filtered(lambda l: l.credit > 0)
            total = sum(debits.mapped('debit'))
            if not total:
                continue
            for d in debits:
                for c in credits:
                    amount = d.debit * c.credit / total
                    key = (d.account_id.id, c.account_id.id)
                    cells[key] = cells.get(key, 0.0) + amount

        currency = self.company_id.currency_id
        lines = []
        for (dr_id, cr_id), amount in cells.items():
            if currency.is_zero(amount):
                continue
            lines.append((0, 0, {
                'debit_account_id': dr_id,
                'credit_account_id': cr_id,
                'amount': amount,
            }))
        self.line_ids = lines
        return True

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})


class L10nUaChessSheetLine(models.Model):
    _name = 'l10n_ua.chess.sheet.line'
    _description = 'Chess Sheet Cell'
    _order = 'debit_account_id, credit_account_id'

    chess_id = fields.Many2one(
        'l10n_ua.chess.sheet', string='Chess Sheet', required=True,
        ondelete='cascade')
    debit_account_id = fields.Many2one(
        'account.account', string='Debit Account', required=True)
    credit_account_id = fields.Many2one(
        'account.account', string='Credit Account', required=True)
    amount = fields.Monetary(string='Amount', currency_field='currency_id')
    currency_id = fields.Many2one(related='chess_id.currency_id')
