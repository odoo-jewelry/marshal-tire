from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nUaTaxPeriodInherit(models.Model):
    _inherit = 'l10n_ua.tax.period'

    closing_id = fields.Many2one(
        'l10n_ua.period.closing',
        string='Closing Entry',
        compute='_compute_closing_id',
    )

    def _compute_closing_id(self):
        Closing = self.env['l10n_ua.period.closing']
        for rec in self:
            rec.closing_id = Closing.search([
                ('period_id', '=', rec.id),
                ('company_id', '=', rec.company_id.id),
                ('state', '=', 'closed'),
            ], limit=1)

    def action_close(self):
        for rec in self:
            if not rec.closing_id:
                raise UserError(_(
                    'Period %s has no closing entry. '
                    'Use Бухгалтерія UA → Звітність → Закриття періоду to close properly.',
                    rec.name,
                ))
        return super().action_close()

    def action_reopen(self):
        for rec in self:
            if rec.closing_id and rec.closing_id.state == 'closed':
                raise UserError(_(
                    'Period %s has an active closing entry. '
                    'Reverse the closing first before reopening.',
                    rec.name,
                ))
        return super().action_reopen()
