from odoo import api, fields, models


class L10nUaKekv(models.Model):
    """Економічна класифікація видатків бюджету (КЕКВ).

    Hierarchical: top-level group codes (2-digit) -> subgroup (3-digit) -> item (4-digit).
    Reference: Наказ Мінфіну № 333 від 12.03.2012 «Інструкція щодо застосування
    економічної класифікації видатків бюджету».
    """
    _name = 'l10n_ua.kekv'
    _description = 'Економічна класифікація видатків (КЕКВ)'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(string='Код КЕКВ', required=True, index=True, size=4,
                       help='2-, 3-, або 4-значний код КЕКВ за наказом Мінфіну № 333')
    name = fields.Char(string='Назва', required=True, translate=True)
    description = fields.Text(string='Опис', translate=True)
    parent_id = fields.Many2one('l10n_ua.kekv', string='Батьківський КЕКВ',
                                ondelete='cascade', index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('l10n_ua.kekv', 'parent_id', string='Дочірні')
    expense_type = fields.Selection([
        ('current', 'Поточні видатки'),
        ('capital', 'Капітальні видатки'),
        ('lending', 'Кредитування'),
    ], string='Тип видатків', help='Поточні (2xxx) / капітальні (3xxx) / кредитування (4xxx)')
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    full_name = fields.Char(compute='_compute_full_name', store=True, recursive=True,
                             help='Повна назва з усіма батьківськими рівнями')

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    @api.depends('name', 'parent_id.full_name')
    def _compute_full_name(self):
        for rec in self:
            if rec.parent_id:
                rec.full_name = f"{rec.parent_id.full_name} / {rec.name}"
            else:
                rec.full_name = rec.name

    _code_uniq = models.Constraint(
        'unique(code)',
        'Код КЕКВ має бути унікальним!',
    )

    _check_no_cycle = models.Constraint(
        "check(parent_id != id)",
        'Категорія не може бути власним батьком!',
    )
