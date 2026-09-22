from odoo import api, fields, models


class L10nUaMealAttendance(models.Model):
    """Облік присутності дітей на харчуванні (для розрахунку фактичних порцій)."""
    _name = 'l10n_ua.meal.attendance'
    _description = 'Відвідуваність харчування'
    _order = 'date desc, group_id'

    date = fields.Date(string='Дата', required=True, default=fields.Date.context_today)
    group_id = fields.Many2one('l10n_ua.education.group', string='Група / клас', required=True)
    company_id = fields.Many2one('res.company',
                                   related='group_id.company_id', store=True, readonly=True)
    enrolled_count = fields.Integer(
        string='Зараховано', compute='_compute_enrolled', store=True,
        help='Кількість дітей у групі станом на дату')
    present_count = fields.Integer(string='Присутні', required=True, default=0)
    absent_count = fields.Integer(
        string='Відсутні', compute='_compute_absent', store=True)
    breakfast_count = fields.Integer(string='Сніданок (порцій)')
    lunch_count = fields.Integer(string='Обід (порцій)')
    afternoon_count = fields.Integer(string='Полуденок (порцій)')
    dinner_count = fields.Integer(string='Вечеря (порцій)')
    note = fields.Char(string='Примітка')

    @api.depends('group_id')
    def _compute_enrolled(self):
        for rec in self:
            rec.enrolled_count = rec.group_id.member_count if rec.group_id else 0

    @api.depends('enrolled_count', 'present_count')
    def _compute_absent(self):
        for rec in self:
            rec.absent_count = max(0, rec.enrolled_count - rec.present_count)

    _date_group_uniq = models.Constraint(
        'unique(date, group_id)',
        'На одну групу — один запис відвідуваності на день!',
    )
