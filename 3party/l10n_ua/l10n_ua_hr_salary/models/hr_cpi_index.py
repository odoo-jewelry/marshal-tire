from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta


class HrCpiIndex(models.Model):
    """Реєстр індексів споживчих цін (ІСЦ) для індексації зарплати.

    Місячний індекс задається у відсотках до попереднього місяця
    (напр. 100.5 = приріст цін 0.5%). Дані оприлюднює Держстат щомісяця.
    """
    _name = 'hr.cpi.index'
    _description = 'Consumer Price Index (для індексації ЗП)'
    _order = 'month desc'
    _rec_name = 'display_name'

    month = fields.Date(
        string='Month',
        required=True,
        help='Місяць індексу (нормалізується до першого числа).'
    )
    index_value = fields.Float(
        string='CPI (%)',
        required=True,
        default=100.0,
        help='Індекс споживчих цін до попереднього місяця, % (напр. 100.5).'
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _unique_month_company = models.Constraint(
        'unique(month, company_id)',
        'Індекс на цей місяць вже існує!',
    )
    _check_positive = models.Constraint(
        'CHECK(index_value > 0)',
        'Індекс споживчих цін має бути додатним!',
    )

    @api.depends('month', 'index_value')
    def _compute_display_name(self):
        for rec in self:
            if rec.month:
                rec.display_name = f"{rec.month.strftime('%m.%Y')} — {rec.index_value:.1f}%"
            else:
                rec.display_name = _('New')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('month'):
                vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('month'):
            vals['month'] = fields.Date.to_date(vals['month']).replace(day=1)
        return super().write(vals)

    @api.model
    def get_indexation_percent(self, base_month, target_month, threshold=101.0,
                               company_id=None):
        """Накопичений % індексації за методом наростаючого підсумку (Порядок №1078).

        Місячні індекси перемножуються, починаючи з місяця, наступного за
        базовим (місяцем останнього підвищення зарплати). Наростаючий індекс
        округлюється до 0.1%. Коли він перевищує поріг (типово 101%), приріст
        (наростаючий − 100) фіксується у сумарному %, а наростання починається
        заново зі 100%. Повертає сумарний % індексації, чинний у target_month.

        Місяці без даних у реєстрі трактуються як 100% (без приросту).
        """
        if not base_month or not target_month:
            return 0.0
        base = fields.Date.to_date(base_month).replace(day=1)
        target = fields.Date.to_date(target_month).replace(day=1)
        if target <= base:
            return 0.0
        if company_id is None:
            company_id = self.env.company.id

        records = self.search([
            ('month', '>', base),
            ('month', '<=', target),
            '|', ('company_id', '=', company_id), ('company_id', '=', False),
        ])
        by_month = {r.month: r.index_value for r in records}

        total_pct = 0.0
        running = 100.0
        cursor = base + relativedelta(months=1)
        while cursor <= target:
            idx = by_month.get(cursor, 100.0)
            running = round(running * idx / 100.0, 1)
            if running > threshold:
                total_pct += running - 100.0
                running = 100.0
            cursor += relativedelta(months=1)
        return round(total_pct, 1)
