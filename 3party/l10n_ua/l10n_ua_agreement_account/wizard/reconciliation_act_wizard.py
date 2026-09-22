"""Акт звірки за конкретним договором (#208)."""

from odoo import fields, models


class ReconciliationActWizard(models.TransientModel):
    _inherit = 'l10n_ua.reconciliation.act.wizard'

    agreement_id = fields.Many2one(
        'agreement',
        string='Договір',
        domain="[('partner_id', '=', partner_id)]",
        help='Обмежити акт звірки одним договором. Якщо не вказано — '
             'звірка за всіма взаєморозрахунками контрагента.',
    )

    def _get_move_line_domain(self):
        """Додати фільтр за договором."""
        domain = super()._get_move_line_domain()
        if self.agreement_id:
            domain.append(('agreement_id', '=', self.agreement_id.id))
        return domain

    def _get_opening_balance(self, account_types):
        """Врахувати договір у розрахунку вхідного сальдо."""
        if not self.agreement_id:
            return super()._get_opening_balance(account_types)
        self.env.cr.execute("""
            SELECT COALESCE(SUM(aml.balance), 0)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            JOIN account_account aa ON aa.id = aml.account_id
            WHERE aml.partner_id = %s
              AND am.state = 'posted'
              AND aml.date < %s
              AND aa.account_type IN %s
              AND aml.agreement_id = %s
        """, (self.partner_id.id, self.date_from, tuple(account_types),
              self.agreement_id.id))
        result = self.env.cr.fetchone()
        return result[0] if result else 0.0
