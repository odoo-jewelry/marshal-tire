from odoo import api, fields, models


class L10nUaKvkv(models.Model):
    """Відомча класифікація видатків — коди головних розпорядників бюджетних коштів (ГРБК).

    3-digit code per ministry / agency (e.g. 220 = МОН, 210 = МОЗ).
    Reference: Бюджетний кодекс України, ст. 8.
    """
    _name = 'l10n_ua.kvkv'
    _description = 'Відомча класифікація видатків (ГРБК)'
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(string='Код КВКВ', required=True, size=3, index=True,
                       help='3-значний код головного розпорядника бюджетних коштів')
    name = fields.Char(string='Назва', required=True, translate=True)
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    _code_uniq = models.Constraint(
        'unique(code)',
        'Код КВКВ має бути унікальним!',
    )
