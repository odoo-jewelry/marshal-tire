"""Спільний звітний період для бюджетних майстрів.

Форми 2д і 2м/4-1д/4-2д/7д/9д однаково питають кошторис і період, однаково
розкладають період на дати й однаково беруть план за цей період. Доки цього
було дві копії, вони встигли розійтися: у 2д план лишався річним навіть на
квартальному звіті.
"""
from odoo import api, fields, models


PERIOD_SELECTION = [
    ('q1', 'I квартал'),
    ('q2', 'II квартал'),
    ('q3', 'III квартал'),
    ('q4', 'IV квартал'),
    ('h1', 'I півріччя'),
    ('9m', '9 місяців'),
    ('year', 'Рік'),
]


class BudgetPeriodMixin(models.AbstractModel):
    _name = 'l10n_ua.budget.period.mixin'
    _description = 'Кошторис і звітний період для бюджетних форм'

    estimate_id = fields.Many2one(
        'l10n_ua.budget.estimate', string='Кошторис', required=True,
        domain="[('state', 'in', ('approved', 'executed', 'closed'))]")
    period = fields.Selection(
        PERIOD_SELECTION, string='Звітний період', default='year', required=True)
    date_from = fields.Date(
        string='Дата з', compute='_compute_dates', store=True, readonly=False)
    date_to = fields.Date(
        string='Дата до', compute='_compute_dates', store=True, readonly=False)

    @api.depends('estimate_id', 'period')
    def _compute_dates(self):
        for w in self:
            if not w.estimate_id:
                w.date_from = w.date_to = False
                continue
            year = w.estimate_id.year
            mapping = {
                'q1': (f'{year}-01-01', f'{year}-03-31'),
                'q2': (f'{year}-04-01', f'{year}-06-30'),
                'q3': (f'{year}-07-01', f'{year}-09-30'),
                'q4': (f'{year}-10-01', f'{year}-12-31'),
                'h1': (f'{year}-01-01', f'{year}-06-30'),
                '9m': (f'{year}-01-01', f'{year}-09-30'),
                'year': (f'{year}-01-01', f'{year}-12-31'),
            }
            df, dt = mapping.get(w.period, mapping['year'])
            w.date_from = fields.Date.from_string(df)
            w.date_to = fields.Date.from_string(dt)

    def _planned_for_period(self, line):
        """План рядка кошторису за обраний період, а не за весь рік.

        Факт беремо за `date_from..date_to`, тож і план має бути за той самий
        проміжок: інакше на квартальних формах «Залишок» і «% виконання»
        рахуються від річного плану — відсоток виходить учетверо занижений.

        Джерело — місячна розкладка кошторису, а не мапа кварталів: дати в
        майстрі `readonly=False`, їх можна виправити руками, і тоді період і
        дати розійшлися б. Місяць враховується цілком, якщо він хоч частково
        потрапляє в діапазон — дрібнішої розкладки, ніж місяць, кошторис не
        має.
        """
        self.ensure_one()
        if not self.date_from or not self.date_to:
            return line.amount_planned
        year = self.estimate_id.year
        if self.date_to.year < year or self.date_from.year > year:
            return 0.0
        first = self.date_from.month if self.date_from.year == year else 1
        last = self.date_to.month if self.date_to.year == year else 12
        return sum(line[f'm{month:02d}'] for month in range(first, last + 1))
