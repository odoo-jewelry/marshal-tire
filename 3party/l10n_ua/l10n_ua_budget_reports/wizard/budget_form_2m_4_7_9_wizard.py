"""Universal wizard for budget reports 2м, 4-1д, 4-2д, 7д, 9д.

Шаблон single QWeb-template з умовним рендерингом дізнається тип за полем
`form_kind`. Логіка агрегації:
* 2м, 4-1д, 4-2д: фільтр по фонду + рік + опційний КПКВК
* 7д: заборгованість по `account.move.line` зі станом 'posted' і
  залишком (debit - credit) > 0
* 9д: дебіторська заборгованість на `asset_receivable` рахунках
"""
from odoo import fields, models, _
from odoo.exceptions import UserError


FORM_KIND = [
    ('2m', 'Форма 2м (загальний фонд місцевого бюджету)'),
    ('4_1d', 'Форма 4-1д (спеціальний фонд)'),
    ('4_2d', 'Форма 4-2д (інші надходження)'),
    ('7d', 'Форма 7д (заборгованість за бюджетними коштами)'),
    ('9d', 'Форма 9д (дебіторська заборгованість)'),
]


class BudgetMultiFormWizard(models.TransientModel):
    _name = 'l10n_ua.budget.multi_form.wizard'
    _description = 'Параметри: 2м / 4-1д / 4-2д / 7д / 9д'
    _inherit = ['l10n_ua.budget.period.mixin']

    form_kind = fields.Selection(FORM_KIND, required=True, default='4_1d')

    def action_print(self):
        self.ensure_one()
        if not self.estimate_id:
            raise UserError(_('Виберіть кошторис.'))
        data = {
            'estimate_id': self.estimate_id.id,
            'form_kind': self.form_kind,
            'form_label': dict(self._fields['form_kind'].selection).get(self.form_kind),
            'period_label': dict(self._fields['period'].selection).get(self.period),
            'date_from': fields.Date.to_string(self.date_from),
            'date_to': fields.Date.to_string(self.date_to),
        }
        report = self.env.ref('l10n_ua_budget_reports.action_report_budget_multi_form')
        return report.report_action(self.estimate_id, data=data)

    def get_report_data(self):
        """Return rows for the selected form kind."""
        self.ensure_one()
        if self.form_kind in ('2m', '4_1d', '4_2d'):
            return self._data_execution_by_fund()
        if self.form_kind == '7d':
            return self._data_payable_debt()
        if self.form_kind == '9d':
            return self._data_receivable_debt()
        return []

    def _data_execution_by_fund(self):
        """План vs факт по фонду — форми 2м, 4-1д, 4-2д."""
        fund_filter = {
            '2m': 'general',
            '4_1d': 'special',
            '4_2d': 'special',  # «інші надходження» — теж спецфонд
        }.get(self.form_kind, 'general')

        AML = self.env['account.move.line']
        out = []
        lines = self.estimate_id.line_ids.filtered(lambda l: l.fund_type == fund_filter)
        for line in lines:
            domain = [
                ('parent_state', '=', 'posted'),
                ('company_id', '=', self.estimate_id.company_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('ua_kekv_id', '=', line.kekv_id.id),
                ('ua_fund_type', '=', fund_filter),
            ]
            if line.kpkvk_id:
                domain.append(('ua_kpkvk_id', '=', line.kpkvk_id.id))
            # Без групування _read_group завжди повертає рівно один кортеж,
            # а сума над порожньою вибіркою приходить як False, не 0.0.
            [(debit, credit)] = AML._read_group(domain, [], ['debit:sum', 'credit:sum'])
            debit = debit or 0.0
            credit = credit or 0.0
            # Для «інших надходжень» (4-2д) — показуємо кредит (надходження), для видатків — дебет
            actual = credit if self.form_kind == '4_2d' else debit
            plan = self._planned_for_period(line)
            variance = plan - actual
            out.append({
                'kekv_code': line.kekv_code,
                'kekv_name': line.kekv_id.name,
                'plan': plan,
                'actual': actual,
                'variance': variance,
                'variance_pct': (actual / plan * 100.0) if plan else 0.0,
            })
        return out

    def _data_payable_debt(self):
        """Форма 7д — кредиторська заборгованість за бюджетними коштами."""
        return self._debt_rows('liability_payable')

    def _data_receivable_debt(self):
        """Форма 9д — дебіторська заборгованість."""
        return self._debt_rows('asset_receivable')

    def _debt_rows(self, account_type):
        """Сальдо розрахунків по КЕКВ і фонду на дату `date_to`.

        7д і 9д відрізняються лише рахунками й знаком сальдо, тож і збираємо
        їх одним місцем: інакше кожна правка тут потребує двох однакових.
        """
        self.ensure_one()
        receivable = account_type == 'asset_receivable'
        AML = self.env['account.move.line']
        domain = [
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.estimate_id.company_id.id),
            ('date', '<=', self.date_to),
            ('account_id.account_type', '=', account_type),
            ('ua_fund_type', '!=', False),
        ]
        # Кошторис складається під конкретну бюджетну програму, тож без цього
        # у звіт потрапляла б заборгованість за всіма програмами установи.
        # Рядки без КПКВК лишаємо: програму часто проставляють на видатковому
        # рядку, а не на рядку розрахунків, і викинути таку заборгованість
        # мовчки гірше, ніж показати її бухгалтеру.
        if self.estimate_id.kpkvk_id:
            domain.append(
                ('ua_kpkvk_id', 'in', [self.estimate_id.kpkvk_id.id, False]))

        currency = self.estimate_id.currency_id
        funds = dict(general='Загальний', special='Спеціальний')
        out = []
        # _read_group віддає групу many2one готовим рекордсетом, тож browse
        # по (id, name) більше не потрібен.
        for kekv, fund_type, debit, credit in AML._read_group(
                domain, ['ua_kekv_id', 'ua_fund_type'], ['debit:sum', 'credit:sum']):
            debit, credit = debit or 0.0, credit or 0.0
            balance = (debit - credit) if receivable else (credit - debit)
            if currency.is_zero(balance):
                continue
            out.append({
                # Рядок без КЕКВ не викидаємо: аналітику часто несе видатковий
                # рядок, а не рядок розрахунків, і мовчки загублена
                # заборгованість гірша за помітну — бухгалтер має побачити, що
                # її треба рознести.
                'kekv_code': kekv.code if kekv else '',
                'kekv_name': kekv.name if kekv else _('Без КЕКВ'),
                'fund': funds.get(fund_type, '—'),
                'balance': balance,
            })
        return out
