from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CurrencySyncWizard(models.TransientModel):
    _name = 'l10n_ua.currency.sync.wizard'
    _description = 'Currency Sync Wizard'

    provider_ids = fields.Many2many(
        'res.currency.rate.provider',
        string='Providers',
        required=True,
        default=lambda self: self.env['res.currency.rate.provider'].search([('active', '=', True)]),
    )

    period_type = fields.Selection(
        selection=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('current_week', 'Current Week'),
            ('previous_week', 'Previous Week'),
            ('current_month', 'Current Month'),
            ('previous_month', 'Previous Month'),
            ('current_quarter', 'Current Quarter'),
            ('previous_quarter', 'Previous Quarter'),
            ('current_year', 'Current Year'),
            ('custom', 'Custom Period'),
        ],
        string='Period',
        default='today',
        required=True,
    )

    date_from = fields.Date(
        string='Date From',
        compute='_compute_dates',
        store=True,
        readonly=False,
    )
    date_to = fields.Date(
        string='Date To',
        compute='_compute_dates',
        store=True,
        readonly=False,
    )

    # Info fields
    days_count = fields.Integer(
        string='Days to Sync',
        compute='_compute_days_count',
    )
    has_nbu = fields.Boolean(
        string='Has NBU Provider',
        compute='_compute_has_nbu',
    )

    @api.depends('period_type')
    def _compute_dates(self):
        today = date.today()
        for rec in self:
            if rec.period_type == 'today':
                rec.date_from = today
                rec.date_to = today
            elif rec.period_type == 'yesterday':
                yesterday = today - timedelta(days=1)
                rec.date_from = yesterday
                rec.date_to = yesterday
            elif rec.period_type == 'current_week':
                # Monday of current week
                rec.date_from = today - timedelta(days=today.weekday())
                rec.date_to = today
            elif rec.period_type == 'previous_week':
                # Previous week Monday to Sunday
                rec.date_from = today - timedelta(days=today.weekday() + 7)
                rec.date_to = today - timedelta(days=today.weekday() + 1)
            elif rec.period_type == 'current_month':
                rec.date_from = today.replace(day=1)
                rec.date_to = today
            elif rec.period_type == 'previous_month':
                first_of_month = today.replace(day=1)
                last_month_end = first_of_month - timedelta(days=1)
                rec.date_from = last_month_end.replace(day=1)
                rec.date_to = last_month_end
            elif rec.period_type == 'current_quarter':
                quarter = (today.month - 1) // 3
                rec.date_from = date(today.year, quarter * 3 + 1, 1)
                rec.date_to = today
            elif rec.period_type == 'previous_quarter':
                quarter = (today.month - 1) // 3
                if quarter == 0:
                    # Q4 of previous year
                    rec.date_from = date(today.year - 1, 10, 1)
                    rec.date_to = date(today.year - 1, 12, 31)
                else:
                    rec.date_from = date(today.year, (quarter - 1) * 3 + 1, 1)
                    end_month = quarter * 3
                    if end_month in (4, 6, 9, 11):
                        end_day = 30
                    elif end_month == 2:
                        end_day = 29 if today.year % 4 == 0 else 28
                    else:
                        end_day = 31
                    rec.date_to = date(today.year, end_month, end_day)
            elif rec.period_type == 'current_year':
                rec.date_from = date(today.year, 1, 1)
                rec.date_to = today
            elif rec.period_type == 'custom':
                # Keep current values or set defaults
                if not rec.date_from:
                    rec.date_from = today
                if not rec.date_to:
                    rec.date_to = today

    @api.depends('date_from', 'date_to')
    def _compute_days_count(self):
        for rec in self:
            if rec.date_from and rec.date_to:
                rec.days_count = (rec.date_to - rec.date_from).days + 1
            else:
                rec.days_count = 0

    @api.depends('provider_ids')
    def _compute_has_nbu(self):
        for rec in self:
            rec.has_nbu = any(p.code == 'nbu' for p in rec.provider_ids)

    def action_sync(self):
        """Execute currency sync."""
        self.ensure_one()

        if not self.provider_ids:
            raise UserError(_("Please select at least one provider."))

        if not self.date_from or not self.date_to:
            raise UserError(_("Please select dates."))

        if self.date_from > self.date_to:
            raise UserError(_("Date From must be before or equal to Date To."))

        if self.date_to > date.today():
            raise UserError(_("Cannot sync future dates."))

        # Check if date range is too large
        delta = (self.date_to - self.date_from).days
        if delta > 365:
            raise UserError(_("Date range cannot exceed 365 days."))

        # Warn if non-NBU providers with date range
        non_nbu_providers = self.provider_ids.filtered(lambda p: p.code != 'nbu')
        if non_nbu_providers and delta > 0:
            # Only NBU supports historical, others will only sync today if in range
            pass  # We'll handle this in the loop

        total_created = 0
        total_updated = 0
        total_skipped = 0
        errors = []

        today = date.today()

        # Sync for each date in range
        current_date = self.date_from
        while current_date <= self.date_to:
            for provider in self.provider_ids:
                try:
                    # NBU supports historical rates, others only current day
                    if provider.code != 'nbu' and current_date != today:
                        continue

                    result = provider._sync_rates(current_date)
                    total_created += result.get('created', 0)
                    total_updated += result.get('updated', 0)
                    total_skipped += result.get('skipped', 0)
                except Exception as e:
                    errors.append(f"{provider.name} ({current_date}): {str(e)}")

            current_date += timedelta(days=1)

        # Build result message
        message_parts = [
            _("Sync completed!"),
            "",
            _("Period: %s to %s (%d days)") % (self.date_from, self.date_to, self.days_count),
            _("Created: %d") % total_created,
            _("Updated: %d") % total_updated,
            _("Skipped: %d") % total_skipped,
        ]

        if non_nbu_providers and delta > 0:
            message_parts.append("")
            message_parts.append(_("Note: %s only support current date rates.") %
                               ', '.join(non_nbu_providers.mapped('name')))

        if errors:
            message_parts.append("")
            message_parts.append(_("Errors:"))
            message_parts.extend(errors[:10])
            if len(errors) > 10:
                message_parts.append(_("... and %d more errors") % (len(errors) - 10))

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Currency Sync'),
                'message': '\n'.join(message_parts),
                'type': 'success' if not errors else 'warning',
                'sticky': True,
            }
        }
