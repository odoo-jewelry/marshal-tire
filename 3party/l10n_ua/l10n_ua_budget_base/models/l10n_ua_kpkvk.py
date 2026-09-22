from odoo import api, fields, models
from odoo.exceptions import ValidationError


class L10nUaKpkvk(models.Model):
    """Програмна класифікація видатків та кредитування бюджету (КПКВК).

    7-digit code: first 3 digits = КВКВ (ГРБК), remaining 4 = program number.
    Per ст. 38 Бюджетного кодексу, programs are approved annually in the budget law.
    Reference: Наказ Мінфіну № 11 від 14.01.2011; updated yearly via річний закон про бюджет.
    """
    _name = 'l10n_ua.kpkvk'
    _description = 'Програмна класифікація видатків (КПКВК)'
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(string='Код КПКВК', required=True, size=7, index=True,
                       help='7-значний код: КВКВ (3 цифри) + програма (4 цифри)')
    name = fields.Char(string='Назва програми', required=True, translate=True)
    kvkv_id = fields.Many2one('l10n_ua.kvkv', string='ГРБК (КВКВ)',
                               compute='_compute_kvkv_id', store=True, index=True)
    kvkv_code = fields.Char(string='Код КВКВ', compute='_compute_kvkv_code', store=True, size=3)
    kfk_id = fields.Many2one('l10n_ua.kfk', string='Функція (КФК)',
                              help='Функціональна класифікація для цієї програми')
    year = fields.Integer(string='Бюджетний рік',
                          help='Рік, на який затверджена програма (КПКВК оновлюється щороку)')
    description = fields.Text(string='Опис', translate=True)
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('code', 'name', 'year')
    def _compute_display_name(self):
        for rec in self:
            parts = []
            if rec.code:
                parts.append(f"[{rec.code}]")
            if rec.name:
                parts.append(rec.name)
            if rec.year:
                parts.append(f"({rec.year})")
            rec.display_name = ' '.join(parts)

    @api.depends('code')
    def _compute_kvkv_code(self):
        for rec in self:
            rec.kvkv_code = rec.code[:3] if rec.code and len(rec.code) >= 3 else False

    @api.depends('kvkv_code')
    def _compute_kvkv_id(self):
        Kvkv = self.env['l10n_ua.kvkv']
        cache = {}
        for rec in self:
            if rec.kvkv_code:
                if rec.kvkv_code not in cache:
                    cache[rec.kvkv_code] = Kvkv.search([('code', '=', rec.kvkv_code)], limit=1)
                rec.kvkv_id = cache[rec.kvkv_code]
            else:
                rec.kvkv_id = False

    @api.constrains('code')
    def _check_code_format(self):
        for rec in self:
            if rec.code and (not rec.code.isdigit() or len(rec.code) != 7):
                raise ValidationError(
                    f"Код КПКВК «{rec.code}» некоректний: очікується рівно 7 цифр.")

    _code_year_uniq = models.Constraint(
        'unique(code, year)',
        'Код КПКВК має бути унікальним у межах одного бюджетного року!',
    )
