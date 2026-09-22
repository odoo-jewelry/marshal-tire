"""Cross-rate through UAH for companies not keeping books in hryvnia — issue #177."""

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCrossRate(TransactionCase):
    """Ukrainian banks quote against UAH; a non-UAH company needs a cross-rate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.date = date(2026, 7, 10)
        cls.usd = cls.env.ref('base.USD')
        cls.eur = cls.env.ref('base.EUR')
        cls.uah = cls.env.ref('base.UAH')
        cls.czk = cls.env.ref('base.CZK')
        (cls.usd + cls.eur + cls.uah + cls.czk).write({'active': True})

        # NBU quotes: 1 unit of the currency costs this many UAH.
        cls.nbu_data = [
            {'cc': 'USD', 'rate': 41.0},
            {'cc': 'EUR', 'rate': 45.0},
            {'cc': 'CZK', 'rate': 1.8},
        ]

    def _make_company(self, name, currency):
        company = self.env['res.company'].create({'name': name})
        company.currency_id = currency
        return company

    def _make_provider(self, company, code='nbu'):
        return self.env['res.currency.rate.provider'].create({
            'name': f'{code} for {company.name}',
            'code': code,
            'company_id': company.id,
        })

    def _rate(self, company, currency):
        return self.env['res.currency.rate'].search([
            ('currency_id', '=', currency.id),
            ('company_id', '=', company.id),
            ('name', '=', self.date),
        ], limit=1)

    def test_uah_company_rate_is_reciprocal(self):
        """Unchanged behaviour for a Ukrainian company: rate = 1 / quote."""
        company = self._make_company('UA Co', self.uah)
        provider = self._make_provider(company)
        result = provider._process_nbu_data(self.nbu_data, self.date)

        self.assertEqual(result['created'], 3)
        usd_rate = self._rate(company, self.usd)
        self.assertAlmostEqual(usd_rate.rate, 1.0 / 41.0, places=9)
        self.assertAlmostEqual(usd_rate.inverse_company_rate, 41.0, places=6)

    def test_non_uah_company_gets_cross_rate(self):
        """CZK company: 1 CZK = 1.8 UAH, 1 USD = 41 UAH → 1 CZK = 1.8/41 USD."""
        company = self._make_company('CZ Co', self.czk)
        provider = self._make_provider(company)
        provider._process_nbu_data(self.nbu_data, self.date)

        usd_rate = self._rate(company, self.usd)
        self.assertAlmostEqual(usd_rate.rate, 1.8 / 41.0, places=9)
        self.assertAlmostEqual(usd_rate.inverse_company_rate, 41.0 / 1.8, places=6)

        eur_rate = self._rate(company, self.eur)
        self.assertAlmostEqual(eur_rate.rate, 1.8 / 45.0, places=9)

    def test_non_uah_company_does_not_get_raw_uah_quote(self):
        """The #177 regression: the raw UAH quote was written as the rate."""
        company = self._make_company('CZ Co raw', self.czk)
        provider = self._make_provider(company)
        provider._process_nbu_data(self.nbu_data, self.date)

        usd_rate = self._rate(company, self.usd)
        self.assertNotAlmostEqual(
            usd_rate.rate, 41.0, places=6,
            msg='Raw UAH quote must never be stored as the company rate',
        )

    def test_company_currency_itself_is_not_written(self):
        """A currency is always worth one of itself; no rate row for CZK."""
        company = self._make_company('CZ Co self', self.czk)
        provider = self._make_provider(company)
        provider._process_nbu_data(self.nbu_data, self.date)

        self.assertFalse(self._rate(company, self.czk))

    def test_unquoted_company_currency_writes_nothing(self):
        """If the provider does not quote the company currency, skip — never guess."""
        company = self._make_company('CZ Co unquoted', self.czk)
        provider = self._make_provider(company)
        data_without_czk = [d for d in self.nbu_data if d['cc'] != 'CZK']

        result = provider._process_nbu_data(data_without_czk, self.date)

        self.assertEqual(result['created'], 0)
        self.assertEqual(result['updated'], 0)
        self.assertFalse(self._rate(company, self.usd))
        self.assertFalse(self._rate(company, self.eur))

    def test_privat_ignores_non_uah_based_pairs(self):
        """PrivatBank publishes non-UAH pairs; they must not pollute the rates."""
        company = self._make_company('UA Co privat', self.uah)
        provider = self._make_provider(company, code='privatbank')
        data = [
            {'ccy': 'USD', 'base_ccy': 'UAH', 'buy': '40.0', 'sale': '42.0'},
            {'ccy': 'EUR', 'base_ccy': 'USD', 'buy': '1.1', 'sale': '1.2'},
        ]
        provider._process_privat_data(data, self.date)

        usd_rate = self._rate(company, self.usd)
        self.assertAlmostEqual(usd_rate.rate, 1.0 / 41.0, places=9)
        self.assertFalse(self._rate(company, self.eur))

    def test_mono_cross_rate(self):
        """Monobank pairs against UAH (980) feed the same cross-rate maths."""
        company = self._make_company('CZ Co mono', self.czk)
        provider = self._make_provider(company, code='monobank')
        data = [
            {'currencyCodeA': 840, 'currencyCodeB': 980, 'rateBuy': 40.0, 'rateSell': 42.0},
            {'currencyCodeA': 203, 'currencyCodeB': 980, 'rateBuy': 1.7, 'rateSell': 1.9},
            {'currencyCodeA': 978, 'currencyCodeB': 840, 'rateCross': 1.1},
        ]
        provider._process_mono_data(data, self.date)

        usd_rate = self._rate(company, self.usd)
        self.assertAlmostEqual(usd_rate.rate, 1.8 / 41.0, places=9)
        # EUR was only quoted against USD, never against UAH
        self.assertFalse(self._rate(company, self.eur))
