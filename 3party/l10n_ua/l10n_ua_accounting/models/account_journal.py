"""Extension of account.journal for Ukrainian cash order and payment order sequences."""

import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AccountJournal(models.Model):
    """Extend account.journal with Ukrainian document sequences."""
    _inherit = 'account.journal'

    # Sequence for PKO (Cash Receipt Orders)
    ua_pko_sequence_id = fields.Many2one(
        'ir.sequence',
        string='PKO Sequence',
        help='Sequence for Ukrainian Cash Receipt Orders (ПКО)',
        copy=False,
    )

    # Sequence for VKO (Cash Disbursement Orders)
    ua_vko_sequence_id = fields.Many2one(
        'ir.sequence',
        string='VKO Sequence',
        help='Sequence for Ukrainian Cash Disbursement Orders (ВКО)',
        copy=False,
    )

    # Sequence for Payment Orders (Платіжні доручення)
    ua_pd_sequence_id = fields.Many2one(
        'ir.sequence',
        string='Payment Order Sequence',
        help='Sequence for Ukrainian Payment Orders (ПД)',
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create sequences for cash and bank journals of Ukrainian companies."""
        journals = super().create(vals_list)

        for journal in journals:
            if not journal.company_id._l10n_ua_is_ukrainian():
                continue
            if journal.type == 'cash':
                journal._create_ua_cash_sequences()
            elif journal.type == 'bank':
                journal._create_ua_bank_sequences()

        return journals

    def _create_ua_cash_sequences(self):
        """Create Ukrainian cash order sequences for this journal."""
        self.ensure_one()
        if self.type != 'cash' or not self.company_id._l10n_ua_is_ukrainian():
            return

        IrSequence = self.env['ir.sequence'].sudo()

        if not self.ua_pko_sequence_id:
            pko_sequence = IrSequence.create({
                'name': f'ПКО - {self.name}',
                'code': f'ua.pko.{self.code or self.id}',
                'prefix': 'ПКО-',
                'padding': 5,
                'company_id': self.company_id.id,
            })
            self.ua_pko_sequence_id = pko_sequence

        if not self.ua_vko_sequence_id:
            vko_sequence = IrSequence.create({
                'name': f'ВКО - {self.name}',
                'code': f'ua.vko.{self.code or self.id}',
                'prefix': 'ВКО-',
                'padding': 5,
                'company_id': self.company_id.id,
            })
            self.ua_vko_sequence_id = vko_sequence

    def _create_ua_bank_sequences(self):
        """Create Ukrainian payment order sequence for this bank journal."""
        self.ensure_one()
        if self.type != 'bank' or not self.company_id._l10n_ua_is_ukrainian():
            return

        if not self.ua_pd_sequence_id:
            pd_sequence = self.env['ir.sequence'].sudo().create({
                'name': f'ПД - {self.name}',
                'code': f'ua.pd.{self.code or self.id}',
                'prefix': 'ПД-',
                'padding': 5,
                'company_id': self.company_id.id,
            })
            self.ua_pd_sequence_id = pd_sequence

    def action_create_ua_sequences(self):
        """Manual action to create UA sequences for existing journals."""
        for journal in self:
            if journal.type == 'cash':
                journal._create_ua_cash_sequences()
            elif journal.type == 'bank':
                journal._create_ua_bank_sequences()
        return True

    @api.model
    def _cron_check_cash_limit(self):
        """Daily cron: check cash balance vs limit for all companies."""
        companies = self.env['res.company'].search([
            ('l10n_ua_cash_limit_enabled', '=', True),
        ])
        for company in companies:
            cash_journals = self.search([
                ('type', '=', 'cash'),
                ('company_id', '=', company.id),
            ])
            for journal in cash_journals:
                balance = journal._get_cash_balance()
                if balance > company.l10n_ua_cash_limit:
                    _logger.warning(
                        'Cash limit exceeded: journal %s (company %s): '
                        'balance %.2f > limit %.2f',
                        journal.name, company.name,
                        balance, company.l10n_ua_cash_limit,
                    )
                    # Post warning to journal chatter
                    journal.message_post(body=_(
                        '⚠️ Ліміт каси перевищено! Залишок: %(balance)s %(currency)s, '
                        'ліміт: %(limit)s %(currency)s.',
                        balance='%.2f' % balance,
                        currency=company.currency_id.name,
                        limit='%.2f' % company.l10n_ua_cash_limit,
                    ))

    def _get_cash_balance(self):
        """Get current cash balance for this journal from posted journal entries."""
        self.ensure_one()
        if not self.default_account_id:
            return 0.0
        self.env.cr.execute("""
            SELECT COALESCE(SUM(debit) - SUM(credit), 0)
            FROM account_move_line aml
            JOIN account_move am ON am.id = aml.move_id
            WHERE aml.account_id = %s
              AND aml.company_id = %s
              AND am.state = 'posted'
        """, (self.default_account_id.id, self.company_id.id))
        return self.env.cr.fetchone()[0]
