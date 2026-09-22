from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    ua_kpkvk_id = fields.Many2one(
        'l10n_ua.kpkvk', string='КПКВК',
        help='Програмна класифікація видатків на рівні документа. '
             'Каскадно пропонується для всіх рядків проводки.')
    ua_fund_type = fields.Selection([
        ('general', 'Загальний фонд'),
        ('special', 'Спеціальний фонд'),
    ], string='Фонд',
       help='Документ-рівневий фонд. Каскадно пропонується для всіх рядків.')

    @api.onchange('ua_kpkvk_id')
    def _onchange_ua_kpkvk_propagate(self):
        if self.ua_kpkvk_id:
            for line in self.line_ids:
                if not line.ua_kpkvk_id:
                    line.ua_kpkvk_id = self.ua_kpkvk_id

    @api.onchange('ua_fund_type')
    def _onchange_ua_fund_type_propagate(self):
        if self.ua_fund_type:
            for line in self.line_ids:
                if not line.ua_fund_type:
                    line.ua_fund_type = self.ua_fund_type
