from odoo import api, fields, models


class L10nUaKfk(models.Model):
    """Функціональна класифікація видатків бюджету (КФК).

    Hierarchical 4-digit code grouped by function:
    XXXX — division.group.class — e.g. 0950 Загальна середня освіта.
    Reference: Наказ Мінфіну № 11 від 14.01.2011 «Про бюджетну класифікацію».
    """
    _name = 'l10n_ua.kfk'
    _description = 'Функціональна класифікація видатків (КФК)'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(string='Код КФК', required=True, size=4, index=True,
                       help='4-значний код функціональної класифікації')
    name = fields.Char(string='Назва', required=True, translate=True)
    parent_id = fields.Many2one('l10n_ua.kfk', string='Батьківська категорія',
                                ondelete='cascade', index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('l10n_ua.kfk', 'parent_id', string='Дочірні')
    division = fields.Char(string='Розділ', compute='_compute_division', store=True,
                            help='Перші 2 цифри коду — розділ функціональної класифікації')
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    @api.depends('code')
    def _compute_division(self):
        for rec in self:
            rec.division = rec.code[:2] if rec.code and len(rec.code) >= 2 else False

    _code_uniq = models.Constraint(
        'unique(code)',
        'Код КФК має бути унікальним!',
    )

    _check_no_cycle = models.Constraint(
        "check(parent_id != id)",
        'Категорія не може бути власним батьком!',
    )
