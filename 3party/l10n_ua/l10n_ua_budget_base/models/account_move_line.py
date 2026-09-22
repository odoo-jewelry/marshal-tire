from odoo import api, fields, models
from odoo.exceptions import ValidationError


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ua_kekv_id = fields.Many2one(
        'l10n_ua.kekv', string='КЕКВ',
        domain="[('child_ids', '=', False)]",
        help='Економічна класифікація видатків для цього рядка проводки. '
             'Дозволені лише листкові коди (без дочірніх).',
        index=True)
    ua_kfk_id = fields.Many2one(
        'l10n_ua.kfk', string='КФК',
        help='Функціональна класифікація видатків.',
        index=True)
    ua_kpkvk_id = fields.Many2one(
        'l10n_ua.kpkvk', string='КПКВК',
        help='Програмна класифікація видатків.',
        index=True)
    ua_kvkv_id = fields.Many2one(
        'l10n_ua.kvkv', string='ГРБК (КВКВ)',
        related='ua_kpkvk_id.kvkv_id', store=True, readonly=True,
        help='Головний розпорядник бюджетних коштів (автоматично з КПКВК).')
    ua_fund_type = fields.Selection([
        ('general', 'Загальний фонд'),
        ('special', 'Спеціальний фонд'),
    ], string='Фонд', index=True,
       help='Загальний або спеціальний фонд бюджету для цього рядка.')

    @api.onchange('account_id')
    def _onchange_account_id_budget(self):
        """Pre-fill budget defaults from the account when adding a line."""
        if self.account_id:
            if not self.ua_kekv_id and self.account_id.ua_default_kekv_id:
                self.ua_kekv_id = self.account_id.ua_default_kekv_id
            if not self.ua_kfk_id and self.account_id.ua_default_kfk_id:
                self.ua_kfk_id = self.account_id.ua_default_kfk_id
            if not self.ua_fund_type and self.account_id.ua_fund_type in ('general', 'special'):
                self.ua_fund_type = self.account_id.ua_fund_type

    @api.constrains('ua_fund_type', 'account_id')
    def _check_fund_matches_account(self):
        """Reject lines whose fund contradicts the account's fund constraint."""
        for line in self:
            account_fund = line.account_id.ua_fund_type
            if (account_fund in ('general', 'special')
                    and line.ua_fund_type
                    and line.ua_fund_type != account_fund):
                raise ValidationError(
                    f"Рахунок {line.account_id.display_name} обмежений "
                    f"фондом «{dict(line.account_id._fields['ua_fund_type'].selection).get(account_fund)}», "
                    f"а в рядку вказано інший фонд.")
