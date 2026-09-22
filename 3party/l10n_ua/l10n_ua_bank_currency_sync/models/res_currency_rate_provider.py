import logging
from datetime import date, datetime

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# API URLs
NBU_API_URL = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"
PRIVAT_API_URL = "https://api.privatbank.ua/p24api/pubinfo"
MONO_API_URL = "https://api.monobank.ua/bank/currency"

# ISO 4217 currency codes mapping for Monobank (uses numeric codes)
MONO_CURRENCY_CODES = {
    980: 'UAH',
    840: 'USD',
    978: 'EUR',
    985: 'PLN',
    826: 'GBP',
    756: 'CHF',
    392: 'JPY',
    156: 'CNY',
    203: 'CZK',
    949: 'TRY',
    208: 'DKK',
    348: 'HUF',
    643: 'RUB',
    933: 'BYN',
    398: 'KZT',
    752: 'SEK',
    578: 'NOK',
    124: 'CAD',
    36: 'AUD',
}


class ResCurrencyRateProvider(models.Model):
    _name = 'res.currency.rate.provider'
    _description = 'Currency Rate Provider'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True)
    code = fields.Selection(
        selection=[
            ('nbu', 'NBU (National Bank of Ukraine)'),
            ('privatbank', 'PrivatBank'),
            ('monobank', 'Monobank'),
        ],
        string='Provider',
        required=True,
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    # Sync settings
    currency_ids = fields.Many2many(
        'res.currency',
        string='Currencies to Sync',
        help='Leave empty to sync all available currencies',
    )
    last_sync_date = fields.Datetime(string='Last Sync', readonly=True)
    auto_sync = fields.Boolean(
        string='Auto Sync',
        default=False,
        help='Automatically sync rates daily via scheduled action',
    )

    # Rate type for PrivatBank
    privat_rate_type = fields.Selection(
        selection=[
            ('5', 'Cash Rate'),
            ('11', 'Non-cash Rate'),
        ],
        string='PrivatBank Rate Type',
        default='5',
        help='Cash rate (5) or Non-cash/Card rate (11)',
    )

    _unique_code_company = models.Constraint(
        'UNIQUE(code, company_id)',
        'Only one provider of each type per company!',
    )

    def action_sync_rates(self):
        """Sync rates from this provider."""
        self.ensure_one()
        return self._sync_rates()

    def _sync_rates(self, target_date=None):
        """Sync currency rates from the provider.

        Args:
            target_date: Date for rates (default: today)

        Returns:
            dict with sync results
        """
        self.ensure_one()

        if target_date is None:
            target_date = date.today()

        if self.code == 'nbu':
            result = self._sync_nbu_rates(target_date)
        elif self.code == 'privatbank':
            result = self._sync_privat_rates(target_date)
        elif self.code == 'monobank':
            result = self._sync_mono_rates(target_date)
        else:
            raise UserError(_("Unknown provider: %s") % self.code)

        self.last_sync_date = fields.Datetime.now()
        return result

    # --- Cross-rate helpers ---

    def _uah_per_company_unit(self, uah_rates):
        """How many UAH one unit of the company currency is worth.

        Ukrainian banks quote every currency against the hryvnia, so a company
        keeping its books in another currency needs a cross-rate through UAH.
        `uah_rates` maps a currency code to UAH per one unit of that currency.

        Returns None when the company currency is not quoted by this provider:
        no cross-rate can be derived, and writing the raw UAH quote instead
        would silently corrupt res.currency.rate.
        """
        self.ensure_one()
        code = self.company_id.currency_id.name
        if code == 'UAH':
            return 1.0
        rate = uah_rates.get(code)
        return rate if rate else None

    def _rate_vals(self, uah_per_unit, uah_per_company_unit):
        """Odoo rate vals for a currency quoted at `uah_per_unit` UAH.

        Odoo stores `rate` as the number of units of the currency bought by one
        unit of the company currency; `inverse_company_rate` is its reciprocal.
        """
        return {
            'rate': uah_per_company_unit / uah_per_unit,
            'inverse_company_rate': uah_per_unit / uah_per_company_unit,
        }

    def _log_missing_company_quote(self, provider_label):
        self.ensure_one()
        _logger.warning(
            "%s provider %r: company currency %s is not quoted against UAH by this "
            "provider, so no cross-rate can be computed. Skipping rate sync for "
            "company %s.",
            provider_label, self.display_name,
            self.company_id.currency_id.name, self.company_id.display_name,
        )

    def _sync_nbu_rates(self, target_date):
        """Sync rates from National Bank of Ukraine.

        API: https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?json&date=YYYYMMDD
        """
        date_str = target_date.strftime('%Y%m%d')
        url = f"{NBU_API_URL}?json&date={date_str}"

        _logger.info("Fetching NBU rates for %s from %s", target_date, url)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise UserError(_("Failed to fetch NBU rates: %s") % str(e))

        if not data:
            raise UserError(_("No rate data returned from NBU for %s") % target_date)

        return self._process_nbu_data(data, target_date)

    def _process_nbu_data(self, data, target_date):
        """Process NBU API response and create/update rates."""
        Currency = self.env['res.currency']
        Rate = self.env['res.currency.rate']

        created = 0
        updated = 0
        skipped = 0

        # Get currencies to sync (or all if empty)
        sync_currencies = self.currency_ids or Currency.search([('active', 'in', [True, False])])
        sync_codes = {c.name: c for c in sync_currencies}

        # NBU quotes: 1 foreign = X UAH
        uah_rates = {
            item['cc']: item['rate']
            for item in data
            if item.get('cc') and item.get('rate')
        }
        uah_per_company_unit = self._uah_per_company_unit(uah_rates)
        if not uah_per_company_unit:
            self._log_missing_company_quote('NBU')
            return {'created': 0, 'updated': 0, 'skipped': len(uah_rates)}

        company_currency = self.company_id.currency_id

        for currency_code, rate in uah_rates.items():
            currency = sync_codes.get(currency_code)
            if not currency:
                skipped += 1
                continue

            if currency == company_currency:
                # A currency is always worth exactly one of itself.
                continue

            rate_vals = self._rate_vals(rate, uah_per_company_unit)

            # Check if rate exists for this date
            existing_rate = Rate.search([
                ('currency_id', '=', currency.id),
                ('name', '=', target_date),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

            if existing_rate:
                existing_rate.write(rate_vals)
                updated += 1
            else:
                Rate.create({
                    'currency_id': currency.id,
                    'name': target_date,
                    'company_id': self.company_id.id,
                    **rate_vals,
                })
                created += 1

        _logger.info("NBU sync complete: %d created, %d updated, %d skipped", created, updated, skipped)
        return {'created': created, 'updated': updated, 'skipped': skipped}

    def _sync_privat_rates(self, target_date):
        """Sync rates from PrivatBank.

        API: https://api.privatbank.ua/p24api/pubinfo?json&exchange&coursid=5
        Note: PrivatBank only provides current rates, not historical.
        """
        coursid = self.privat_rate_type or '5'
        url = f"{PRIVAT_API_URL}?json&exchange&coursid={coursid}"

        _logger.info("Fetching PrivatBank rates from %s", url)

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise UserError(_("Failed to fetch PrivatBank rates: %s") % str(e))

        if not data:
            raise UserError(_("No rate data returned from PrivatBank"))

        return self._process_privat_data(data, target_date)

    def _process_privat_data(self, data, target_date):
        """Process PrivatBank API response."""
        Currency = self.env['res.currency']
        Rate = self.env['res.currency.rate']

        created = 0
        updated = 0
        skipped = 0

        sync_currencies = self.currency_ids or Currency.search([('active', 'in', [True, False])])
        sync_codes = {c.name: c for c in sync_currencies}

        # PrivatBank quotes buy/sale; only pairs based on UAH are usable here.
        uah_rates = {}
        for item in data:
            currency_code = item.get('ccy')
            base_ccy = item.get('base_ccy')
            if not currency_code or (base_ccy and base_ccy != 'UAH'):
                continue
            buy_rate = float(item.get('buy', 0))
            sale_rate = float(item.get('sale', 0))
            if not buy_rate:
                continue
            uah_rates[currency_code] = (buy_rate + sale_rate) / 2 if sale_rate else buy_rate

        uah_per_company_unit = self._uah_per_company_unit(uah_rates)
        if not uah_per_company_unit:
            self._log_missing_company_quote('PrivatBank')
            return {'created': 0, 'updated': 0, 'skipped': len(uah_rates)}

        company_currency = self.company_id.currency_id

        for currency_code, avg_rate in uah_rates.items():
            currency = sync_codes.get(currency_code)
            if not currency:
                skipped += 1
                continue

            if currency == company_currency:
                continue

            rate_vals = self._rate_vals(avg_rate, uah_per_company_unit)

            existing_rate = Rate.search([
                ('currency_id', '=', currency.id),
                ('name', '=', target_date),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

            if existing_rate:
                existing_rate.write(rate_vals)
                updated += 1
            else:
                Rate.create({
                    'currency_id': currency.id,
                    'name': target_date,
                    'company_id': self.company_id.id,
                    **rate_vals,
                })
                created += 1

        _logger.info("PrivatBank sync complete: %d created, %d updated, %d skipped", created, updated, skipped)
        return {'created': created, 'updated': updated, 'skipped': skipped}

    def _sync_mono_rates(self, target_date):
        """Sync rates from Monobank.

        API: https://api.monobank.ua/bank/currency
        Note: Monobank only provides current rates, not historical.
        Rate limit: max 1 request per minute.
        """
        _logger.info("Fetching Monobank rates from %s", MONO_API_URL)

        try:
            response = requests.get(MONO_API_URL, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            raise UserError(_("Failed to fetch Monobank rates: %s") % str(e))

        if not data:
            raise UserError(_("No rate data returned from Monobank"))

        return self._process_mono_data(data, target_date)

    def _process_mono_data(self, data, target_date):
        """Process Monobank API response."""
        Currency = self.env['res.currency']
        Rate = self.env['res.currency.rate']

        created = 0
        updated = 0
        skipped = 0

        sync_currencies = self.currency_ids or Currency.search([('active', 'in', [True, False])])
        sync_codes = {c.name: c for c in sync_currencies}

        # Monobank returns pairs, we only want rates against UAH (980)
        uah_code = 980

        uah_rates = {}
        for item in data:
            # Only process pairs where one side is UAH
            if item.get('currencyCodeB') != uah_code:
                continue

            currency_code = MONO_CURRENCY_CODES.get(item.get('currencyCodeA'))
            if not currency_code:
                skipped += 1
                continue

            # Monobank provides rateBuy and rateSell; rateCross when it does not
            buy_rate = item.get('rateBuy', 0)
            sell_rate = item.get('rateSell', 0)
            if not buy_rate:
                buy_rate = item.get('rateCross', 0)
            if not sell_rate:
                sell_rate = item.get('rateCross', buy_rate)

            if not buy_rate:
                skipped += 1
                continue

            uah_rates[currency_code] = (buy_rate + sell_rate) / 2 if sell_rate else buy_rate

        uah_per_company_unit = self._uah_per_company_unit(uah_rates)
        if not uah_per_company_unit:
            self._log_missing_company_quote('Monobank')
            return {'created': 0, 'updated': 0, 'skipped': skipped + len(uah_rates)}

        company_currency = self.company_id.currency_id

        for currency_code, avg_rate in uah_rates.items():
            currency = sync_codes.get(currency_code)
            if not currency:
                skipped += 1
                continue

            if currency == company_currency:
                continue

            rate_vals = self._rate_vals(avg_rate, uah_per_company_unit)

            existing_rate = Rate.search([
                ('currency_id', '=', currency.id),
                ('name', '=', target_date),
                ('company_id', '=', self.company_id.id),
            ], limit=1)

            if existing_rate:
                existing_rate.write(rate_vals)
                updated += 1
            else:
                Rate.create({
                    'currency_id': currency.id,
                    'name': target_date,
                    'company_id': self.company_id.id,
                    **rate_vals,
                })
                created += 1

        _logger.info("Monobank sync complete: %d created, %d updated, %d skipped", created, updated, skipped)
        return {'created': created, 'updated': updated, 'skipped': skipped}

    @api.model
    def _cron_sync_rates(self):
        """Scheduled action to sync rates from all active providers."""
        providers = self.search([('auto_sync', '=', True), ('active', '=', True)])
        for provider in providers:
            try:
                provider._sync_rates()
            except Exception as e:
                _logger.error("Failed to sync rates from %s: %s", provider.name, str(e))
