from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


MEMBER_STATE_SELECTION = [
    ('applicant', 'Заявник'),
    ('enrolled', 'Зараховано'),
    ('studying', 'Навчається'),
    ('on_leave', 'Академвідпустка'),
    ('graduated', 'Випущено'),
    ('expelled', 'Відраховано'),
    ('transferred', 'Переведено в інший заклад'),
]


class L10nUaEducationContingentMember(models.Model):
    """Член контингенту: учень / студент / вихованець.

    Прив'язується до `res.partner` як до фізособи. Опційно може бути також
    прив'язаний до `hr.employee` (якщо це працівник, який паралельно
    навчається — наприклад, аспірант-науковий співробітник).
    """
    _name = 'l10n_ua.education.contingent.member'
    _description = 'Член контингенту (учень / студент / вихованець)'
    _order = 'state, partner_id'
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    partner_id = fields.Many2one(
        'res.partner', string='Фізособа', required=True,
        ondelete='restrict', tracking=True,
        help='Фізична особа — учень/студент. Контактні дані, ПІБ, адреса — у партнера.')
    employee_id = fields.Many2one(
        'hr.employee', string='Працівник',
        help='Якщо ця особа паралельно є працівником закладу — посилання сюди.')
    member_type = fields.Selection([
        ('pupil', 'Учень'),
        ('student', 'Студент'),
        ('pupil_zdo', 'Вихованець (ЗДО)'),
        ('cadet', 'Курсант'),
        ('postgrad', 'Аспірант / докторант'),
        ('listener', 'Слухач'),
    ], string='Тип', required=True, default='pupil', tracking=True)
    state = fields.Selection(
        MEMBER_STATE_SELECTION, string='Стан', default='applicant', required=True,
        tracking=True, index=True)
    company_id = fields.Many2one(
        'res.company', string='Установа', required=True,
        default=lambda self: self.env.company, tracking=True)
    academic_year_id = fields.Many2one(
        'l10n_ua.education.academic.year', string='Навчальний рік',
        ondelete='restrict')
    group_id = fields.Many2one(
        'l10n_ua.education.group', string='Група / клас', ondelete='set null',
        tracking=True, index=True,
        domain="[('academic_year_id', '=', academic_year_id)]")
    student_number = fields.Char(string='Особова справа / № студентського',
                                  help='Внутрішній номер особової справи учня/студента',
                                  index=True, copy=False, tracking=True)

    # Lifecycle dates
    date_application = fields.Date(string='Дата подання заяви', tracking=True)
    date_enrolled = fields.Date(string='Дата зарахування', tracking=True, copy=False)
    date_graduated = fields.Date(string='Дата випуску', tracking=True, copy=False)
    date_expelled = fields.Date(string='Дата відрахування', tracking=True, copy=False)

    # Reason / order
    enrollment_order_no = fields.Char(string='Наказ про зарахування', copy=False)
    graduation_order_no = fields.Char(string='Наказ про випуск', copy=False)
    expulsion_reason = fields.Text(string='Причина відрахування', copy=False)

    display_name = fields.Char(compute='_compute_display_name', store=True)
    active = fields.Boolean(default=True)

    @api.depends('partner_id', 'group_id', 'state')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.partner_id:
                parts.append(rec.partner_id.name)
            if rec.group_id:
                parts.append(f"({rec.group_id.name})")
            rec.display_name = ' '.join(parts) if parts else _('Новий')

    _student_number_company_uniq = models.Constraint(
        'unique(student_number, company_id)',
        'Номер особової справи має бути унікальним у межах установи!',
    )

    # === State machine ===

    def _can_transition(self, from_state, to_state):
        allowed = {
            'applicant': {'enrolled', 'expelled'},
            'enrolled': {'studying', 'expelled', 'transferred'},
            'studying': {'on_leave', 'graduated', 'expelled', 'transferred'},
            'on_leave': {'studying', 'expelled'},
            # Terminal states allow no further transitions
        }
        return to_state in allowed.get(from_state, set())

    def _do_transition(self, to_state, date_field=None, error_msg=None):
        for rec in self:
            if not rec._can_transition(rec.state, to_state):
                raise UserError(error_msg or _(
                    'Не можна перейти зі стану «%(f)s» у «%(t)s».',
                    f=dict(self._fields['state'].selection).get(rec.state),
                    t=dict(self._fields['state'].selection).get(to_state)))
            vals = {'state': to_state}
            if date_field and not rec[date_field]:
                vals[date_field] = fields.Date.context_today(rec)
            rec.write(vals)

    def action_enroll(self):
        self._do_transition('enrolled', date_field='date_enrolled')

    def action_start_studying(self):
        self._do_transition('studying')

    def action_take_leave(self):
        self._do_transition('on_leave')

    def action_return_from_leave(self):
        self._do_transition('studying')

    def action_graduate(self):
        self._do_transition('graduated', date_field='date_graduated')

    def action_expel(self):
        self._do_transition('expelled', date_field='date_expelled')

    def action_transfer(self):
        self._do_transition('transferred')

    @api.constrains('group_id', 'academic_year_id')
    def _check_group_matches_year(self):
        for rec in self:
            if rec.group_id and rec.academic_year_id \
                    and rec.group_id.academic_year_id != rec.academic_year_id:
                raise ValidationError(_(
                    'Група «%(g)s» належить до іншого навчального року, ніж учень/студент.',
                    g=rec.group_id.name))
