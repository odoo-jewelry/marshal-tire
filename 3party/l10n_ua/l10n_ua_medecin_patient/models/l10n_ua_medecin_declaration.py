from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


STATE_SELECTION = [
    ('draft', 'Чернетка'),
    ('active', 'Активна'),
    ('terminated', 'Розірвана'),
    ('cancelled', 'Скасована'),
]

TERMINATION_REASON = [
    ('patient_choice', 'За власним бажанням пацієнта'),
    ('doctor_left', 'Лікар припинив роботу в закладі'),
    ('patient_relocation', 'Переїзд пацієнта'),
    ('death', 'Смерть пацієнта'),
    ('other', 'Інше'),
]


class L10nUaMedecinDeclaration(models.Model):
    """Декларація пацієнта з лікарем ПМД.

    Регулюється Наказом МОЗ № 503 від 19.03.2018. Один пацієнт у конкретний
    момент часу може мати лише одну активну декларацію.
    """
    _name = 'l10n_ua.medecin.declaration'
    _description = 'Декларація з лікарем ПМД'
    _order = 'date_start desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Номер', required=True, copy=False,
                       default='Нова', tracking=True)
    state = fields.Selection(STATE_SELECTION, default='draft', required=True,
                              tracking=True, copy=False)
    patient_id = fields.Many2one(
        'l10n_ua.medecin.patient', string='Пацієнт', required=True,
        ondelete='restrict', tracking=True, index=True)
    doctor_id = fields.Many2one(
        'hr.employee', string='Лікар', required=True,
        ondelete='restrict', tracking=True, index=True,
        help='Лікар ПМД, з яким укладається декларація.')
    company_id = fields.Many2one(
        'res.company', string='Заклад', required=True,
        default=lambda self: self.env.company, tracking=True)
    date_signed = fields.Date(string='Дата підписання', tracking=True,
                                default=fields.Date.context_today)
    date_start = fields.Date(string='Дата набрання чинності', tracking=True)
    date_terminated = fields.Date(string='Дата припинення', tracking=True, copy=False)
    termination_reason = fields.Selection(
        TERMINATION_REASON, string='Підстава припинення', tracking=True, copy=False)
    termination_note = fields.Text(string='Деталі припинення')
    ehealth_uuid = fields.Char(
        string='UUID в eHealth', copy=False,
        help='Унікальний ідентифікатор декларації в Центральній компоненті eHealth.')
    is_signed_electronic = fields.Boolean(
        string='Підписана електронно (МЕДОК/eHealth)',
        help='Чи зареєстрована декларація в eHealth із електронним підписом.')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Нова') == 'Нова':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'l10n_ua.medecin.declaration') or 'Нова'
        return super().create(vals_list)

    # === State machine ===

    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Активувати можна лише чернетку.'))
            # Terminate any other active declaration for the same patient
            other_active = self.search([
                ('patient_id', '=', rec.patient_id.id),
                ('state', '=', 'active'),
                ('id', '!=', rec.id),
            ])
            if other_active:
                other_active.write({
                    'state': 'terminated',
                    'date_terminated': fields.Date.context_today(rec),
                    'termination_reason': 'patient_choice',
                    'termination_note': _(
                        'Автоматично припинено через підписання нової декларації %s', rec.name),
                })
            rec.write({
                'state': 'active',
                'date_start': rec.date_start or fields.Date.context_today(rec),
            })

    def action_terminate(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_('Припиняти можна лише активну декларацію.'))
            if not rec.termination_reason:
                raise UserError(_('Вкажіть підставу припинення декларації.'))
            rec.write({
                'state': 'terminated',
                'date_terminated': fields.Date.context_today(rec),
            })

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'active'):
                raise UserError(_('Скасовувати можна лише чернетку або активну декларацію.'))
            rec.state = 'cancelled'

    @api.constrains('date_start', 'date_terminated')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_terminated and rec.date_start > rec.date_terminated:
                raise ValidationError(_('Дата припинення не може передувати даті початку.'))

    _ehealth_uuid_uniq = models.Constraint(
        'unique(ehealth_uuid)',
        'UUID eHealth має бути унікальним!',
    )
