from odoo import api, fields, models


class L10nUaTreasuryOrgan(models.Model):
    """Територіальний орган Державної казначейської служби України.

    Включає центральний апарат, обласні ГУДКСУ, ГУДКСУ Києва і Севастополя.
    Районні УДКСУ є дочірніми (parent_id) до обласного органу.
    """
    _name = 'l10n_ua.treasury.organ'
    _description = 'Орган Державної казначейської служби'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(string='Код органу', required=True, index=True, size=10,
                       help='Внутрішній код територіального органу ДКСУ')
    name = fields.Char(string='Назва', required=True, translate=True)
    organ_type = fields.Selection([
        ('central', 'Центральний апарат'),
        ('regional', 'Головне управління (область)'),
        ('district', 'Управління (район/місто)'),
    ], string='Тип органу', required=True, default='regional')
    state_id = fields.Many2one(
        'res.country.state', string='Область',
        domain="[('country_id.code', '=', 'UA')]",
        help='Область, де знаходиться орган (для районних — область, до якої входить район)')
    parent_id = fields.Many2one(
        'l10n_ua.treasury.organ', string='Підпорядкування',
        ondelete='restrict', index=True,
        help='Вищий за рангом орган (для районних УДКСУ — обласне ГУДКСУ)')
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('l10n_ua.treasury.organ', 'parent_id', string='Підлеглі')
    address = fields.Char(string='Адреса')
    phone = fields.Char(string='Телефон')
    edrpou = fields.Char(string='ЄДРПОУ', size=10)
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    _code_uniq = models.Constraint(
        'unique(code)',
        'Код органу ДКСУ має бути унікальним!',
    )
