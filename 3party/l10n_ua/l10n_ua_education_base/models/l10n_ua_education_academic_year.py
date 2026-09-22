from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nUaEducationAcademicYear(models.Model):
    """Навчальний рік (наприклад «2025/2026»).

    Для шкіл і ВНЗ навчальний рік стартує 01.09 і закінчується 30.06–31.08
    наступного календарного року. Для ЗДО можна налаштувати інші дати.
    """
    _name = 'l10n_ua.education.academic.year'
    _description = 'Навчальний рік'
    _order = 'date_start desc'
    _rec_name = 'name'

    name = fields.Char(string='Назва', required=True,
                       help='Наприклад «2025/2026»')
    year_start = fields.Integer(
        string='Рік початку', required=True,
        help='Календарний рік, у якому починається навчальний рік (наприклад 2025 для «2025/2026»)')
    year_end = fields.Integer(
        string='Рік закінчення', compute='_compute_year_end', store=True,
        help='Календарний рік закінчення = year_start + 1')
    date_start = fields.Date(string='Дата початку', required=True)
    date_end = fields.Date(string='Дата закінчення', required=True)
    is_active = fields.Boolean(
        string='Поточний',
        help='Чи є цей навчальний рік активним. Лише один рік може бути активним одночасно.')
    company_id = fields.Many2one('res.company', string='Установа', required=True,
                                  default=lambda self: self.env.company)
    state = fields.Selection([
        ('planned', 'Планується'),
        ('active', 'Активний'),
        ('closed', 'Закритий'),
    ], string='Стан', default='planned', required=True)
    notes = fields.Text(string='Примітки')

    @api.depends('year_start')
    def _compute_year_end(self):
        for rec in self:
            rec.year_end = (rec.year_start or 0) + 1

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_start >= rec.date_end:
                raise ValidationError(_('Дата початку має бути раніше дати закінчення.'))

    @api.constrains('is_active', 'company_id')
    def _check_only_one_active(self):
        for rec in self:
            if rec.is_active:
                duplicate = self.search([
                    ('id', '!=', rec.id),
                    ('is_active', '=', True),
                    ('company_id', '=', rec.company_id.id),
                ], limit=1)
                if duplicate:
                    raise ValidationError(_(
                        'У межах установи може бути лише один активний навчальний рік. '
                        'Зараз активний: %(name)s', name=duplicate.name))

    _year_company_uniq = models.Constraint(
        'unique(year_start, company_id)',
        'Навчальний рік має бути унікальним для установи!',
    )
