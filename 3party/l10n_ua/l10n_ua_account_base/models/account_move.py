from odoo import api, fields, models

from ..tools.formatters import amount_to_words_ua


class AccountMove(models.Model):
    _inherit = 'account.move'

    ua_doc_type = fields.Selection(
        selection=[
            ('invoice', 'Invoice (Рахунок)'),
            ('tax_invoice', 'Tax Invoice (Податкова накладна)'),
            ('adjustment', 'Adjustment (Розрахунок коригування)'),
            ('act', 'Act (Акт виконаних робіт)'),
            ('ttn', 'TTN (Товарно-транспортна накладна)'),
            ('pko', 'PKO (Прибутковий касовий ордер)'),
            ('vko', 'VKO (Видатковий касовий ордер)'),
            ('bank', 'Bank Statement (Банківська виписка)'),
            ('advance', 'Advance Report (Авансовий звіт)'),
            ('other', 'Other'),
        ],
        string='UA Document Type',
    )
    ua_doc_number = fields.Char(
        string='UA Document Number',
        help='Document number in Ukrainian format',
    )
    ua_doc_date = fields.Date(
        string='UA Document Date',
        help='Document date (may differ from accounting date)',
    )
    ua_counterparty_doc = fields.Char(
        string='Counterparty Document',
        help='Counterparty document number',
    )
    l10n_ua_amount_words = fields.Char(
        string='Amount in Words (UA)',
        compute='_compute_l10n_ua_amount_words',
    )
    l10n_ua_discount_total = fields.Monetary(
        string='Discount Total',
        compute='_compute_l10n_ua_discount_total',
        currency_field='currency_id',
    )

    @api.depends('amount_total', 'currency_id')
    def _compute_l10n_ua_amount_words(self):
        for move in self:
            if move.currency_id and move.currency_id.name == 'UAH':
                move.l10n_ua_amount_words = amount_to_words_ua(
                    move.amount_total, currency='UAH',
                )
            else:
                move.l10n_ua_amount_words = ''

    @api.depends('invoice_line_ids.discount', 'invoice_line_ids.price_unit',
                 'invoice_line_ids.quantity')
    def _compute_l10n_ua_discount_total(self):
        for move in self:
            total = 0.0
            for line in move.invoice_line_ids:
                if line.discount:
                    total += line.price_unit * line.quantity * line.discount / 100.0
            move.l10n_ua_discount_total = total
