from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _post(self, soft=True):
        """Hook into posting to enforce budget limits for treasury journals."""
        treasury_moves = self.filtered(
            lambda m: m.journal_id.ua_is_treasury
            and m.journal_id.ua_treasury_check_limit)
        if treasury_moves:
            checker = self.env['l10n_ua.budget.limit.checker']
            for move in treasury_moves:
                checker.check_move_against_limits(move)
        return super()._post(soft=soft)
