from odoo import api, fields, models

from ..tools.formatters import format_date_ua, format_money_ua, amount_to_words_ua


class L10nUaDocumentMixin(models.AbstractModel):
    _name = 'l10n_ua.document.mixin'
    _description = 'Ukrainian Document Mixin'

    ua_doc_number = fields.Char(
        string='Document Number',
    )
    ua_doc_date = fields.Date(
        string='Document Date',
    )

    def get_formatted_date(self, date=None, format_type='long'):
        """Get formatted date in Ukrainian.
        
        Args:
            date: Date to format (default: ua_doc_date)
            format_type: 'long' for "15" січня 2026 р., 'short' for 15.01.2026
        """
        if date is None:
            date = self.ua_doc_date
        return format_date_ua(date, format_type)

    def get_formatted_money(self, amount, currency='UAH'):
        """Get formatted money amount."""
        return format_money_ua(amount, currency)

    def get_amount_in_words(self, amount, currency='UAH'):
        """Get amount in words in Ukrainian."""
        return amount_to_words_ua(amount, currency)
