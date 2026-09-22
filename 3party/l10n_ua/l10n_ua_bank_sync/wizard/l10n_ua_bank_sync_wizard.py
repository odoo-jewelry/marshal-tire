from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nUaBankSyncWizard(models.TransientModel):
    _name = 'l10n_ua.bank.sync.wizard'
    _description = 'Bank Sync Wizard'

    config_id = fields.Many2one(
        'l10n_ua.bank.sync.config',
        string='Bank Configuration',
        required=True,
    )
    date_from = fields.Date(
        string='Date From',
        required=True,
        compute='_compute_dates_from_last_job',
        store=True,
        readonly=False,
    )
    date_to = fields.Date(
        string='Date To',
        required=True,
        compute='_compute_dates_from_last_job',
        store=True,
        readonly=False,
    )
    last_job_id = fields.Many2one(
        'l10n_ua.bank.sync.job',
        string='Last Job',
        compute='_compute_last_job',
    )

    @api.depends('config_id')
    def _compute_last_job(self):
        for wizard in self:
            if not wizard.config_id:
                wizard.last_job_id = False
                continue
            wizard.last_job_id = self.env['l10n_ua.bank.sync.job'].search([
                ('config_id', '=', wizard.config_id.id),
                ('state', '=', 'done'),
            ], limit=1, order='date_to desc')

    @api.depends('config_id')
    def _compute_dates_from_last_job(self):
        for wizard in self:
            if not wizard.config_id:
                wizard.date_from = fields.Date.today() - timedelta(days=7)
                wizard.date_to = fields.Date.today()
                continue

            # Find last completed job for this config
            last_job = self.env['l10n_ua.bank.sync.job'].search([
                ('config_id', '=', wizard.config_id.id),
                ('state', '=', 'done'),
            ], limit=1, order='date_to desc')

            if last_job:
                # Set date_from to last job's date_to + 1 day
                wizard.date_from = last_job.date_to + timedelta(days=1)
                wizard.date_to = fields.Date.today()
            else:
                # No previous job - default to last 7 days
                wizard.date_from = fields.Date.today() - timedelta(days=7)
                wizard.date_to = fields.Date.today()

    # Quick select buttons
    period = fields.Selection(
        selection=[
            ('from_last', 'From Last Sync'),
            ('custom', 'Custom Period'),
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('last_7_days', 'Last 7 Days'),
            ('last_30_days', 'Last 30 Days'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
        ],
        string='Quick Select',
        default='from_last',
    )

    @api.onchange('period')
    def _onchange_period(self):
        today = fields.Date.today()

        if self.period == 'from_last':
            # Set dates from last completed job
            if self.last_job_id:
                self.date_from = self.last_job_id.date_to + timedelta(days=1)
                self.date_to = today
            else:
                # No previous job - default to last 7 days
                self.date_from = today - timedelta(days=7)
                self.date_to = today
        elif self.period == 'today':
            self.date_from = today
            self.date_to = today
        elif self.period == 'yesterday':
            yesterday = today - timedelta(days=1)
            self.date_from = yesterday
            self.date_to = yesterday
        elif self.period == 'last_7_days':
            self.date_from = today - timedelta(days=7)
            self.date_to = today
        elif self.period == 'last_30_days':
            self.date_from = today - timedelta(days=30)
            self.date_to = today
        elif self.period == 'this_month':
            self.date_from = today.replace(day=1)
            self.date_to = today
        elif self.period == 'last_month':
            first_of_this_month = today.replace(day=1)
            last_of_prev_month = first_of_this_month - timedelta(days=1)
            self.date_from = last_of_prev_month.replace(day=1)
            self.date_to = last_of_prev_month

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from > rec.date_to:
                raise UserError(_("Date From must be before Date To"))

    def action_sync(self):
        """Create and run sync job."""
        self.ensure_one()
        return self.config_id._create_and_run_job(self.date_from, self.date_to)
