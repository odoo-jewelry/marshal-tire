import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


STATE_SELECTION = [
    ('draft', 'Чернетка'),
    ('submitted', 'Подано в НСЗУ'),
    ('active', 'Чинний'),
    ('expired', 'Завершений'),
    ('terminated', 'Розірваний'),
]

# Капітаційні коефіцієнти за віковими категоріями (приблизні згідно Постанови № 240).
# Значення можна перевизначити в рядку договору.
AGE_COEFFICIENTS = {
    '0_5': 4.0,
    '6_17': 2.2,
    '18_39': 1.0,
    '40_64': 1.2,
    '65+': 2.5,
}


class L10nUaMedecinNszuContract(models.Model):
    """Договір з НСЗУ на пакети медичних послуг.

    Реальний договір з НСЗУ обʼєднує кілька пакетів (наприклад, ПМД-капітація
    + специфікації). Цей документ агрегує їх з підрахунком очікуваних
    надходжень.
    """
    _name = 'l10n_ua.medecin.nszu.contract'
    _description = 'Договір з НСЗУ'
    _order = 'date_start desc, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Номер', required=True, copy=False, default='Новий',
                       tracking=True)
    state = fields.Selection(STATE_SELECTION, default='draft', required=True,
                              tracking=True, copy=False)
    company_id = fields.Many2one('res.company', required=True,
                                  default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id',
                                    store=True, readonly=True)
    nszu_contract_no = fields.Char(string='Номер договору НСЗУ', tracking=True,
                                     help='Номер договору, присвоєний НСЗУ.')
    date_signed = fields.Date(string='Дата підписання', tracking=True)
    date_start = fields.Date(string='Дата початку', required=True, tracking=True)
    date_end = fields.Date(string='Дата закінчення', required=True, tracking=True)
    notes = fields.Html(string='Примітки')
    line_ids = fields.One2many('l10n_ua.medecin.nszu.contract.line', 'contract_id',
                                 string='Пакети в договорі', copy=True)
    total_expected = fields.Monetary(
        string='Очікувані надходження', currency_field='currency_id',
        compute='_compute_total', store=True)

    @api.depends('line_ids.expected_amount')
    def _compute_total(self):
        for rec in self:
            rec.total_expected = sum(rec.line_ids.mapped('expected_amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Новий') == 'Новий':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'l10n_ua.medecin.nszu.contract') or 'Новий'
        return super().create(vals_list)

    # === State machine ===

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Подати можна лише чернетку.'))
            if not rec.line_ids:
                raise UserError(_('Договір повинен містити хоча б один пакет.'))
            rec.state = 'submitted'

    def action_activate(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Активувати можна лише поданий договір.'))
            rec.state = 'active'

    def action_expire(self):
        for rec in self:
            if rec.state != 'active':
                raise UserError(_('Завершити можна лише чинний договір.'))
            rec.state = 'expired'

    def action_terminate(self):
        for rec in self:
            if rec.state not in ('active', 'submitted'):
                raise UserError(_('Розірвати можна лише поданий або чинний договір.'))
            rec.state = 'terminated'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state not in ('submitted', 'terminated'):
                raise UserError(_('Повернути в чернетку можна лише поданий або розірваний договір.'))
            rec.state = 'draft'


class L10nUaMedecinNszuContractLine(models.Model):
    """Рядок договору з НСЗУ — один пакет."""
    _name = 'l10n_ua.medecin.nszu.contract.line'
    _description = 'Рядок договору з НСЗУ'
    _order = 'contract_id, package_id'

    contract_id = fields.Many2one('l10n_ua.medecin.nszu.contract', required=True,
                                    ondelete='cascade', index=True)
    company_id = fields.Many2one(related='contract_id.company_id', store=True, readonly=True)
    currency_id = fields.Many2one(related='contract_id.currency_id', store=True, readonly=True)
    package_id = fields.Many2one('l10n_ua.medecin.nszu.package', string='Пакет', required=True)
    payment_model = fields.Selection(related='package_id.payment_model', store=True, readonly=True)
    tariff = fields.Monetary(string='Тариф', currency_field='currency_id',
                              help='Тариф за одиницю. За замовчуванням = базовий тариф пакета.')
    expected_units = fields.Integer(
        string='Очікувана кількість',
        help='Кількість декларацій (для капітації) / випадків / послуг.')
    expected_amount = fields.Monetary(
        string='Очікувано', currency_field='currency_id',
        compute='_compute_expected_amount', store=True)
    note = fields.Char(string='Примітка')

    @api.depends('tariff', 'expected_units')
    def _compute_expected_amount(self):
        for line in self:
            line.expected_amount = (line.tariff or 0) * (line.expected_units or 0)

    @api.onchange('package_id')
    def _onchange_package(self):
        if self.package_id and not self.tariff:
            self.tariff = self.package_id.base_tariff

    def action_compute_pmd_capitation(self):
        """Перерахувати expected_units на основі активних декларацій з ваговими коефіцієнтами."""
        Patient = self.env['l10n_ua.medecin.patient']
        for line in self:
            if line.payment_model != 'capitation':
                continue
            # _read_group повертає кортежі (значення_групування..., агрегати...),
            # тому розпакування позиційне, без ключів на кшталт '<поле>_count'.
            groups = Patient._read_group(
                [('company_id', '=', line.company_id.id),
                 ('active_declaration_id', '!=', False)],
                ['age_category'], ['__count'])
            weighted = 0.0
            unclassified = 0
            for category, count in groups:
                # Пацієнт без дати народження не має вікової категорії, і
                # `.get(category, 1.0)` мовчки рахував би його як 18–39.
                # Вгадувати коефіцієнт для капітації не можна: це гроші НСЗУ
                # за декларацію, яку не можна віднести до жодної групи. Так
                # само з категорією, якій не задано коефіцієнта — краще
                # недорахувати й сказати про це, ніж підставити 1.0 навмання.
                coefficient = AGE_COEFFICIENTS.get(category)
                if not coefficient:
                    unclassified += count
                    continue
                weighted += count * coefficient
            if unclassified:
                _logger.warning(
                    'Капітація ПМД (%s): %s декларацій не враховано — у '
                    'пацієнтів немає дати народження або їхній віковій '
                    'категорії не задано коефіцієнта',
                    line.contract_id.display_name, unclassified)
            line.expected_units = int(round(weighted))
