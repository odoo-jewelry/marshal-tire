from odoo import api, fields, models


class L10nUaMedecinIcd10(models.Model):
    """МКХ-10 довідник (Міжнародна класифікація хвороб, 10-та редакція)."""
    _name = 'l10n_ua.medecin.icd10'
    _description = 'МКХ-10 код'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'code'
    _rec_name = 'display_name'

    code = fields.Char(string='Код', required=True, index=True,
                       help='Формат: A00.0, B15-B19 (блок) тощо')
    name = fields.Char(string='Назва', required=True, translate=True)
    block = fields.Char(string='Блок', help='Наприклад A00-A09')
    parent_id = fields.Many2one('l10n_ua.medecin.icd10', ondelete='cascade', index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many('l10n_ua.medecin.icd10', 'parent_id')
    description = fields.Text(string='Опис')
    active = fields.Boolean(default=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    @api.depends('code', 'name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.code}] {rec.name}" if rec.code else rec.name

    _code_uniq = models.Constraint(
        'unique(code)',
        'Код МКХ-10 має бути унікальним!',
    )
