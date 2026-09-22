from odoo import api, fields, models


class L10nUaEducationGroup(models.Model):
    """Навчальна група (клас / курс / група / гурток).

    Універсальна модель — для ЗДО це група («Сонечко»), для школи клас («3-А»),
    для коледжу/ВНЗ — курсова група («ПЗ-21-1»).
    """
    _name = 'l10n_ua.education.group'
    _description = 'Навчальна група / клас / курс'
    _order = 'academic_year_id desc, level, name'

    name = fields.Char(string='Назва групи', required=True,
                       help='Наприклад «3-А», «ПЗ-21-1», «Сонечко»')
    code = fields.Char(string='Код', help='Внутрішній код, опційно')
    academic_year_id = fields.Many2one(
        'l10n_ua.education.academic.year', string='Навчальний рік', required=True,
        default=lambda self: self._default_academic_year(),
        ondelete='restrict', index=True)
    group_type = fields.Selection([
        ('zdo_group', 'Група ЗДО'),
        ('class', 'Шкільний клас'),
        ('course_group', 'Курсова група (ВНЗ/коледж)'),
        ('pto_group', 'Група ПТУ'),
        ('extracurricular', 'Гурток / секція'),
        ('other', 'Інше'),
    ], string='Тип', required=True, default='class')
    level = fields.Integer(string='Рівень (клас/курс)',
                           help='Номер класу (1-11/12) або курсу (1-6).')
    profile = fields.Char(string='Профіль навчання',
                          help='Напрям/спеціальність — для шкіл з профільним навчанням, '
                               'для ПТУ/ВНЗ — спеціальність.')
    capacity = fields.Integer(string='Розрахункова чисельність',
                               help='Планова кількість учнів/студентів у групі.')
    company_id = fields.Many2one(
        'res.company', string='Установа',
        related='academic_year_id.company_id', store=True, readonly=True)
    teacher_id = fields.Many2one(
        'hr.employee', string='Класний керівник / куратор')
    member_ids = fields.One2many(
        'l10n_ua.education.contingent.member', 'group_id',
        string='Учні / Студенти')
    member_count = fields.Integer(
        string='Зарахованих', compute='_compute_member_count', store=False)
    active = fields.Boolean(default=True)

    @api.model
    def _default_academic_year(self):
        return self.env['l10n_ua.education.academic.year'].search([
            ('is_active', '=', True),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

    @api.depends('member_ids')
    def _compute_member_count(self):
        for grp in self:
            grp.member_count = len(grp.member_ids.filtered(
                lambda m: m.state in ('enrolled', 'studying')))
