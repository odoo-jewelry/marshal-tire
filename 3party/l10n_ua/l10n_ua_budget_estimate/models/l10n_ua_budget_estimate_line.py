from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nUaBudgetEstimateLine(models.Model):
    """Рядок кошторису: один КЕКВ × фонд × період × сума.

    Розпис здійснюється помісячно (12 чисел m01..m12) — квартальні і річний
    підсумки обчислюються автоматично. Касове виконання беремо з
    `account.move.line` за тим же роком/КЕКВ/фондом/КПКВК.
    """
    _name = 'l10n_ua.budget.estimate.line'
    _description = 'Рядок кошторису'
    _order = 'estimate_id, fund_type, kekv_code'

    estimate_id = fields.Many2one(
        'l10n_ua.budget.estimate', required=True, ondelete='cascade', index=True)
    state = fields.Selection(
        related='estimate_id.state', store=True, readonly=True)
    year = fields.Integer(related='estimate_id.year', store=True, readonly=True)
    company_id = fields.Many2one(
        related='estimate_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(
        related='estimate_id.currency_id', store=True, readonly=True)
    kpkvk_id = fields.Many2one(
        'l10n_ua.kpkvk', string='КПКВК',
        help='Програмна класифікація. За замовчуванням з шапки кошторису.')
    kekv_id = fields.Many2one(
        'l10n_ua.kekv', string='КЕКВ', required=True,
        domain="[('child_ids', '=', False)]",
        help='Економічна класифікація. Дозволено лише листкові коди (без дочірніх).')
    kekv_code = fields.Char(
        related='kekv_id.code', store=True, readonly=True, index=True)
    fund_type = fields.Selection(
        [('general', 'Загальний фонд'), ('special', 'Спеціальний фонд')],
        string='Фонд', required=True, default='general', index=True)
    name = fields.Char(string='Призначення', help='Стислий опис призначення видатку.')

    # Monthly breakdown
    m01 = fields.Monetary(string='Січень', currency_field='currency_id')
    m02 = fields.Monetary(string='Лютий', currency_field='currency_id')
    m03 = fields.Monetary(string='Березень', currency_field='currency_id')
    m04 = fields.Monetary(string='Квітень', currency_field='currency_id')
    m05 = fields.Monetary(string='Травень', currency_field='currency_id')
    m06 = fields.Monetary(string='Червень', currency_field='currency_id')
    m07 = fields.Monetary(string='Липень', currency_field='currency_id')
    m08 = fields.Monetary(string='Серпень', currency_field='currency_id')
    m09 = fields.Monetary(string='Вересень', currency_field='currency_id')
    m10 = fields.Monetary(string='Жовтень', currency_field='currency_id')
    m11 = fields.Monetary(string='Листопад', currency_field='currency_id')
    m12 = fields.Monetary(string='Грудень', currency_field='currency_id')

    # Quarterly aggregates
    q1 = fields.Monetary(
        string='I кв.', currency_field='currency_id',
        compute='_compute_quarters', store=True)
    q2 = fields.Monetary(
        string='II кв.', currency_field='currency_id',
        compute='_compute_quarters', store=True)
    q3 = fields.Monetary(
        string='III кв.', currency_field='currency_id',
        compute='_compute_quarters', store=True)
    q4 = fields.Monetary(
        string='IV кв.', currency_field='currency_id',
        compute='_compute_quarters', store=True)

    amount_planned = fields.Monetary(
        string='Усього план', currency_field='currency_id',
        compute='_compute_quarters', store=True,
        help='Річний план = сума всіх 12 місяців.')
    amount_actual = fields.Monetary(
        string='Касове виконання', currency_field='currency_id',
        compute='_compute_amount_actual', store=True)
    variance = fields.Monetary(
        string='Залишок', currency_field='currency_id',
        compute='_compute_variance', store=True,
        help='План − касове виконання. Від\'ємне значення = перевиконання плану.')
    execution_percent = fields.Float(
        string='% виконання', compute='_compute_variance', store=True)

    @api.depends('m01', 'm02', 'm03', 'm04', 'm05', 'm06',
                  'm07', 'm08', 'm09', 'm10', 'm11', 'm12')
    def _compute_quarters(self):
        for line in self:
            line.q1 = line.m01 + line.m02 + line.m03
            line.q2 = line.m04 + line.m05 + line.m06
            line.q3 = line.m07 + line.m08 + line.m09
            line.q4 = line.m10 + line.m11 + line.m12
            line.amount_planned = line.q1 + line.q2 + line.q3 + line.q4

    @api.depends('year', 'kekv_id', 'fund_type', 'kpkvk_id',
                  'estimate_id.company_id', 'estimate_id.state')
    def _compute_amount_actual(self):
        """Aggregate posted journal lines matching this estimate line's analytic key."""
        AML = self.env['account.move.line']
        for line in self:
            if not (line.year and line.kekv_id and line.fund_type):
                line.amount_actual = 0.0
                continue
            domain = [
                ('parent_state', '=', 'posted'),
                ('company_id', '=', line.company_id.id),
                ('date', '>=', f'{line.year}-01-01'),
                ('date', '<=', f'{line.year}-12-31'),
                ('ua_kekv_id', '=', line.kekv_id.id),
                ('ua_fund_type', '=', line.fund_type),
            ]
            if line.kpkvk_id:
                domain.append(('ua_kpkvk_id', '=', line.kpkvk_id.id))
            # Sum debit (expenditures) by convention for budget execution.
            # Без групування _read_group завжди повертає рівно один кортеж,
            # а сума над порожньою вибіркою приходить як False, не 0.0.
            [(debit,)] = AML._read_group(domain, [], ['debit:sum'])
            line.amount_actual = debit or 0.0

    @api.depends('amount_planned', 'amount_actual')
    def _compute_variance(self):
        for line in self:
            line.variance = line.amount_planned - line.amount_actual
            line.execution_percent = (
                line.amount_actual / line.amount_planned * 100.0
                if line.amount_planned else 0.0)

    @api.onchange('estimate_id')
    def _onchange_estimate_default_kpkvk(self):
        if self.estimate_id and not self.kpkvk_id and self.estimate_id.kpkvk_id:
            self.kpkvk_id = self.estimate_id.kpkvk_id

    @api.constrains('m01', 'm02', 'm03', 'm04', 'm05', 'm06',
                     'm07', 'm08', 'm09', 'm10', 'm11', 'm12')
    def _check_non_negative(self):
        months = ('m01', 'm02', 'm03', 'm04', 'm05', 'm06',
                  'm07', 'm08', 'm09', 'm10', 'm11', 'm12')
        for line in self:
            for m in months:
                if line[m] < 0:
                    raise ValidationError(_(
                        'Сума за %(m)s не може бути від\'ємною (рядок КЕКВ %(k)s).',
                        m=m, k=line.kekv_id.code or '?'))

    @api.constrains('estimate_id', 'fund_type')
    def _check_fund_matches_header(self):
        """If estimate header restricts the fund, lines must match."""
        for line in self:
            header_fund = line.estimate_id.fund_type
            if header_fund in ('general', 'special') and line.fund_type != header_fund:
                raise ValidationError(_(
                    'Кошторис обмежений «%(h)s», а рядок має фонд «%(l)s».',
                    h=dict(line.estimate_id._fields['fund_type'].selection).get(header_fund),
                    l=dict(line._fields['fund_type'].selection).get(line.fund_type)))
