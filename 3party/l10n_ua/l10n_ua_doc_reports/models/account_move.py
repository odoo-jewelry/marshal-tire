from odoo import api, models

from odoo.addons.l10n_ua_account_base.tools.formatters import (
    amount_to_words_ua,
    format_date_ua,
)


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_ua_report_lines(self):
        """Return invoice lines excluding sections and notes."""
        return self.invoice_line_ids.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )

    def _get_ua_date_formatted(self, dt=None):
        """Format date in Ukrainian long format: "15" січня 2026 р."""
        return format_date_ua(dt or self.invoice_date or self.date)

    def _get_ua_tax_amount_words(self):
        """Amount in words for VAT portion."""
        if self.amount_tax and self.currency_id.name == 'UAH':
            return amount_to_words_ua(self.amount_tax)
        return ''
