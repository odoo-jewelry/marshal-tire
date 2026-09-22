from odoo import api, fields, models

from odoo.addons.l10n_ua_account_base.tools.formatters import (
    amount_to_words_ua,
    format_date_ua,
)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    l10n_ua_amount_words = fields.Char(
        string='Amount in Words (UA)',
        compute='_compute_l10n_ua_amount_words',
    )

    @api.depends('amount_total', 'currency_id')
    def _compute_l10n_ua_amount_words(self):
        for order in self:
            if order.currency_id and order.currency_id.name == 'UAH':
                order.l10n_ua_amount_words = amount_to_words_ua(
                    order.amount_total, currency='UAH',
                )
            else:
                order.l10n_ua_amount_words = ''

    def _get_ua_report_lines(self):
        """Return order lines excluding sections and notes."""
        return self.order_line.filtered(
            lambda l: l.display_type not in ('line_section', 'line_note')
        )

    def _get_ua_date_formatted(self, dt=None):
        """Format date in Ukrainian long format."""
        return format_date_ua(dt or self.date_order.date())
