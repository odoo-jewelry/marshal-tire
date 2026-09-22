from odoo import api, fields, models, _
from odoo.exceptions import UserError

MONTHS = range(1, 13)


class L10nUaGeneralLedger(models.Model):
    _name = 'l10n_ua.general.ledger'
    _description = 'General Ledger (Головна книга)'
    _order = 'year desc'

    name = fields.Char(compute='_compute_name', store=True)
    year = fields.Integer(
        string='Year', required=True,
        default=lambda self: fields.Date.context_today(self).year)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    line_ids = fields.One2many(
        'l10n_ua.general.ledger.line', 'ledger_id', string='Lines')
    state = fields.Selection(
        selection=[('draft', 'Draft'), ('confirmed', 'Confirmed')],
        string='State', default='draft')

    @api.depends('year')
    def _compute_name(self):
        for rec in self:
            rec.name = _('Головна книга %s') % (rec.year or '')

    def action_compute(self):
        """Побудувати Головну книгу: по кожному рахунку — початкове сальдо,
        помісячні обороти Дт/Кт і кінцеве сальдо за рік."""
        self.ensure_one()
        if not self.year:
            raise UserError(_('Вкажіть рік.'))

        self.line_ids.unlink()
        AML = self.env['account.move.line']
        year_start = fields.Date.to_date('%04d-01-01' % self.year)
        year_end = fields.Date.to_date('%04d-12-31' % self.year)
        base = [
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]

        # account.id -> accumulator
        data = {}

        def bucket(account):
            return data.setdefault(account.id, {
                'account': account,
                'opening': 0.0,
                'months': {m: {'debit': 0.0, 'credit': 0.0} for m in MONTHS},
            })

        # Початкове сальдо: чистий рух до початку року.
        for account, balance in AML._read_group(
                base + [('date', '<', year_start)],
                ['account_id'], ['balance:sum']):
            bucket(account)['opening'] += balance or 0.0

        # Помісячні обороти Дт/Кт за рік.
        for account, month, debit, credit in AML._read_group(
                base + [('date', '>=', year_start), ('date', '<=', year_end)],
                ['account_id', 'date:month'],
                ['debit:sum', 'credit:sum']):
            acc = bucket(account)
            acc['months'][month.month]['debit'] += debit or 0.0
            acc['months'][month.month]['credit'] += credit or 0.0

        currency = self.company_id.currency_id
        lines = []
        for acc in data.values():
            opening = acc['opening']
            total_debit = sum(acc['months'][m]['debit'] for m in MONTHS)
            total_credit = sum(acc['months'][m]['credit'] for m in MONTHS)
            if (currency.is_zero(opening) and currency.is_zero(total_debit)
                    and currency.is_zero(total_credit)):
                continue
            closing = opening + total_debit - total_credit
            vals = {
                'account_id': acc['account'].id,
                'opening_debit': opening if opening > 0 else 0.0,
                'opening_credit': -opening if opening < 0 else 0.0,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'closing_debit': closing if closing > 0 else 0.0,
                'closing_credit': -closing if closing < 0 else 0.0,
            }
            for m in MONTHS:
                vals['m%02d_debit' % m] = acc['months'][m]['debit']
                vals['m%02d_credit' % m] = acc['months'][m]['credit']
            lines.append((0, 0, vals))
        self.line_ids = lines
        return True

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_draft(self):
        self.write({'state': 'draft'})


def _month_field(month, side):
    return fields.Monetary(
        string='%02d-%s' % (month, side.title()), currency_field='currency_id')


class L10nUaGeneralLedgerLine(models.Model):
    _name = 'l10n_ua.general.ledger.line'
    _description = 'General Ledger Line'
    _order = 'account_id'

    ledger_id = fields.Many2one(
        'l10n_ua.general.ledger', string='Ledger', required=True,
        ondelete='cascade')
    account_id = fields.Many2one(
        'account.account', string='Account', required=True)
    currency_id = fields.Many2one(related='ledger_id.currency_id')

    opening_debit = fields.Monetary(string='Opening Dr', currency_field='currency_id')
    opening_credit = fields.Monetary(string='Opening Cr', currency_field='currency_id')
    total_debit = fields.Monetary(string='Turnover Dr', currency_field='currency_id')
    total_credit = fields.Monetary(string='Turnover Cr', currency_field='currency_id')
    closing_debit = fields.Monetary(string='Closing Dr', currency_field='currency_id')
    closing_credit = fields.Monetary(string='Closing Cr', currency_field='currency_id')

    # Помісячні обороти Дт/Кт (m01_debit … m12_credit).
    m01_debit = _month_field(1, 'debit'); m01_credit = _month_field(1, 'credit')
    m02_debit = _month_field(2, 'debit'); m02_credit = _month_field(2, 'credit')
    m03_debit = _month_field(3, 'debit'); m03_credit = _month_field(3, 'credit')
    m04_debit = _month_field(4, 'debit'); m04_credit = _month_field(4, 'credit')
    m05_debit = _month_field(5, 'debit'); m05_credit = _month_field(5, 'credit')
    m06_debit = _month_field(6, 'debit'); m06_credit = _month_field(6, 'credit')
    m07_debit = _month_field(7, 'debit'); m07_credit = _month_field(7, 'credit')
    m08_debit = _month_field(8, 'debit'); m08_credit = _month_field(8, 'credit')
    m09_debit = _month_field(9, 'debit'); m09_credit = _month_field(9, 'credit')
    m10_debit = _month_field(10, 'debit'); m10_credit = _month_field(10, 'credit')
    m11_debit = _month_field(11, 'debit'); m11_credit = _month_field(11, 'credit')
    m12_debit = _month_field(12, 'debit'); m12_credit = _month_field(12, 'credit')
