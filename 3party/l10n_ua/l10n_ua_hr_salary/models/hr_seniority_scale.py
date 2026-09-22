from odoo import models, fields, api


class HrSeniorityScale(models.Model):
    """Шкала надбавки за вислугу років (стаж → відсоток).

    Розмір надбавки за вислугу років у комерційному секторі визначається
    роботодавцем (колдоговором / положенням про оплату праці). Модель дозволяє
    налаштувати ступінчасту шкалу: за кожен поріг стажу — свій відсоток.
    """
    _name = 'hr.seniority.scale'
    _description = 'Шкала надбавки за вислугу років'

    name = fields.Char(string='Назва', required=True, default='Основна шкала')
    company_id = fields.Many2one(
        'res.company', string='Компанія',
        default=lambda self: self.env.company)
    line_ids = fields.One2many(
        'hr.seniority.scale.line', 'scale_id', string='Ступені')
    active = fields.Boolean(default=True)

    def get_percent(self, years):
        """Відсоток надбавки для заданого стажу (років).

        Береться ступінь із найбільшим порогом years_from, що не перевищує
        фактичний стаж. Якщо жоден поріг не досягнутий — 0.
        """
        self.ensure_one()
        percent = 0.0
        best_from = -1.0
        for line in self.line_ids:
            if line.years_from <= years and line.years_from > best_from:
                best_from = line.years_from
                percent = line.percent
        return percent


class HrSeniorityScaleLine(models.Model):
    _name = 'hr.seniority.scale.line'
    _description = 'Ступінь шкали вислуги років'
    _order = 'years_from'

    scale_id = fields.Many2one(
        'hr.seniority.scale', string='Шкала', required=True, ondelete='cascade')
    years_from = fields.Integer(
        string='Стаж від (років)', required=True,
        help='Мінімальний стаж у роках, з якого діє цей відсоток надбавки.')
    percent = fields.Float(
        string='Відсоток надбавки, %', required=True,
        help='Надбавка у відсотках до посадового окладу / тарифної ставки.')

    _percent_positive = models.Constraint(
        'CHECK(percent >= 0)',
        'Відсоток надбавки не може бути відʼємним.')
    _years_positive = models.Constraint(
        'CHECK(years_from >= 0)',
        'Стаж не може бути відʼємним.')

    @api.depends('years_from', 'percent')
    def _compute_display_name(self):
        for line in self:
            line.display_name = 'від %s р. — %s%%' % (line.years_from, line.percent)
