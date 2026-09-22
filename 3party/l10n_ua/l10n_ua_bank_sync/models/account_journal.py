import json
from datetime import datetime, timedelta

from babel.dates import format_date

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import get_lang


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    # Dashboard fields
    ua_bank_balance = fields.Monetary(
        string='Current Balance',
        compute='_compute_ua_bank_dashboard',
        currency_field='currency_id',
    )
    ua_bank_balance_graph = fields.Text(
        string='Balance Graph Data',
        compute='_compute_ua_bank_dashboard',
    )
    ua_bank_statement_count = fields.Integer(
        string='Statement Count',
        compute='_compute_ua_bank_dashboard',
    )
    ua_bank_last_sync = fields.Datetime(
        string='Last Sync',
        compute='_compute_ua_bank_dashboard',
    )
    ua_bank_has_online_config = fields.Boolean(
        compute='_compute_ua_bank_configs')
    ua_bank_has_file_config = fields.Boolean(
        compute='_compute_ua_bank_configs')

    def _compute_ua_bank_configs(self):
        Config = self.env['l10n_ua.bank.sync.config']
        for journal in self:
            configs = Config.search([('journal_id', '=', journal.id)])
            types = set(configs.mapped('exchange_type'))
            journal.ua_bank_has_online_config = 'online' in types
            journal.ua_bank_has_file_config = 'file' in types

    def _compute_ua_bank_dashboard(self):
        """Compute dashboard data. No @api.depends - always recompute on access."""
        Line = self.env['account.bank.statement.line']

        for journal in self:
            if journal.type != 'bank':
                journal.ua_bank_balance = 0
                journal.ua_bank_balance_graph = '[]'
                journal.ua_bank_statement_count = 0
                journal.ua_bank_last_sync = False
                continue

            # Get native bank statement lines for this journal
            transactions = Line.search([
                ('journal_id', '=', journal.id),
            ], order='date desc, id desc')

            # Current balance (sum of all amounts)
            journal.ua_bank_balance = sum(transactions.mapped('amount'))

            # Transaction count (shown as "Statements" in UI for familiarity)
            journal.ua_bank_statement_count = len(transactions)

            # Last sync date
            last_job = self.env['l10n_ua.bank.sync.job'].search([
                ('journal_id', '=', journal.id),
                ('state', '=', 'done'),
            ], limit=1, order='write_date desc')
            journal.ua_bank_last_sync = last_job.write_date if last_job else False

            # Build graph data in Odoo dashboard_graph format
            journal.ua_bank_balance_graph = json.dumps(
                journal._get_ua_bank_graph_data(transactions)
            )

    def _get_ua_bank_graph_data(self, transactions):
        """
        Get balance graph data in Odoo dashboard_graph format.
        If more than 10 records in last 30 days - show last 30 days.
        If less than 10 records in last 30 days - show last 10 records.

        Returns format expected by dashboard_graph widget:
        [{'values': [{'x': 'label', 'y': value, 'name': 'full_label'}...],
          'title': 'Graph Title', 'key': 'Key', 'area': True, 'color': '#xxx'}]
        """
        locale = get_lang(self.env).code
        currency = self.currency_id or self.company_id.currency_id

        def build_point(date_obj, amount):
            name = format_date(date_obj, 'd LLLL Y', locale=locale)
            short_name = format_date(date_obj, 'd MMM', locale=locale)
            return {'x': short_name, 'y': currency.round(amount), 'name': name}

        if not transactions:
            # Return empty graph structure
            return [{
                'values': [],
                'title': _('Balance'),
                'key': _('Balance'),
                'area': True,
                'color': '#7c7bad',
            }]

        today = fields.Date.today()
        date_30_days_ago = today - timedelta(days=30)

        # Count records in last 30 days
        trans_30_days = transactions.filtered(lambda t: t.date and t.date >= date_30_days_ago)

        if len(trans_30_days) >= 10:
            # Show last 30 days - group by date
            selected_trans = trans_30_days
        else:
            # Show last 10 records
            selected_trans = transactions[:10]

        if not selected_trans:
            return [{
                'values': [],
                'title': _('Balance'),
                'key': _('Balance'),
                'area': True,
                'color': '#7c7bad',
            }]

        # Group by date and calculate amounts per day
        date_amounts = {}
        for trans in selected_trans:
            if trans.date:
                if trans.date not in date_amounts:
                    date_amounts[trans.date] = 0
                date_amounts[trans.date] += trans.amount

        # Sort by date and build cumulative balance (oldest to newest)
        sorted_dates = sorted(date_amounts.keys())

        # Build graph data with cumulative balance
        graph_values = []
        cumulative = 0
        for date_obj in sorted_dates:
            cumulative += date_amounts[date_obj]
            graph_values.append(build_point(date_obj, cumulative))

        return [{
            'values': graph_values,
            'title': _('Balance'),
            'key': _('Balance'),
            'area': True,
            'color': '#7c7bad',
        }]

    def action_open_transactions(self):
        """Open native bank statement lines for this journal."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transactions'),
            'res_model': 'account.bank.statement.line',
            'view_mode': 'list,form',
            'domain': [('journal_id', '=', self.id)],
            'context': {'default_journal_id': self.id},
        }

    def action_open_bank_statements(self):
        """Open native bank statements for this journal."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bank Statements'),
            'res_model': 'account.bank.statement',
            'view_mode': 'list,form',
            'domain': [('journal_id', '=', self.id)],
            'context': {'default_journal_id': self.id},
        }

    def action_import_bank_file(self):
        """Відкрити майстер імпорту виписки з файлу для файлового конфігу журналу."""
        self.ensure_one()
        config = self.env['l10n_ua.bank.sync.config'].search([
            ('journal_id', '=', self.id),
            ('exchange_type', '=', 'file'),
        ], limit=1)
        if not config:
            raise UserError(_(
                'Для журналу «%s» немає файлової конфігурації обміну. '
                'Створіть конфіг із файловим провайдером (напр. VST Bank).'
            ) % self.name)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Імпорт виписки з файлу'),
            'res_model': 'l10n_ua.bank.statement.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_config_id': config.id},
        }

    def action_new_sync_job(self):
        """Create new sync job for this journal (online providers only)."""
        self.ensure_one()
        config = self.env['l10n_ua.bank.sync.config'].search([
            ('journal_id', '=', self.id),
            ('exchange_type', '=', 'online'),
        ], limit=1)

        if not config:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Configure Bank Sync',
                'res_model': 'l10n_ua.bank.sync.config',
                'view_mode': 'form',
                'context': {'default_journal_id': self.id},
            }

        # Find last job for this config
        last_job = self.env['l10n_ua.bank.sync.job'].search([
            ('config_id', '=', config.id),
            ('state', '=', 'done'),
        ], limit=1, order='date_to desc')

        context = {'default_config_id': config.id}

        if last_job:
            # Set date_from to last job's date_to + 1 day
            context['default_date_from'] = last_job.date_to + timedelta(days=1)
            context['default_date_to'] = fields.Date.today()

        return {
            'type': 'ir.actions.act_window',
            'name': _('New Sync Job'),
            'res_model': 'l10n_ua.bank.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': context,
        }
