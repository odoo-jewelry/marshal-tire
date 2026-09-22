"""Нарахування зарплати в іноземній валюті (#206)."""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import tagged
from .common import SalaryTestCase


@tagged('post_install', '-at_install')
class TestSalaryCurrency(SalaryTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.psp_params.write({'min_hourly_wage': 0.0})
        cls.usd = cls.env.ref('base.USD')
        # Курс потрібен не лише щоб отримати число: без жодного запису курсу
        # розрахунок тепер відмовляється рахувати валютний оклад.
        #
        # Червень 2025 — рівні 40.0, щоб очікувані суми в тестах читались
        # усно (1000 USD → 40 000 грн), а не звірялись із калькулятором.
        cls.env['res.currency.rate'].create({
            'name': '2025-06-01',
            'currency_id': cls.usd.id,
            'company_id': cls.company.id,
            'inverse_company_rate': 40.0,
        })
        # 2026-й — офіційні курси НБУ на 1 число місяця. Вересня й далі тут
        # немає навмисно: на момент написання їх ще не існувало, і саме на
        # цьому тримається тест про місяць без курсу.
        cls.env['res.currency.rate'].create([
            {'name': f'2026-{month:02d}-01',
             'currency_id': cls.usd.id,
             'company_id': cls.company.id,
             'inverse_company_rate': rate}
            for month, rate in enumerate(
                (42.3532, 42.8483, 43.2081, 43.9175,
                 43.9630, 44.2680, 44.7917, 44.6916), start=1)
        ])
        # Тип нарахування SALARY (окладна форма)
        if not cls.env['hr.accrual.type'].search([('code', '=', 'SALARY')], limit=1):
            cls.env['hr.accrual.type'].create({
                'name': 'Оклад', 'code': 'SALARY', 'category': 'wage'})

    def _payslip(self):
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2025, 6, 1),
            'date_to': date(2025, 6, 30),
        })
        slip.write({
            'scheduled_hours': 160.0, 'scheduled_days': 20,
            'worked_days': 20, 'worked_hours': 160.0,
        })
        return slip

    def _salary_accrual(self, slip):
        return slip.accrual_ids.filtered(
            lambda a: a.accrual_type_id.code == 'SALARY')

    def test_company_currency_rate_one(self):
        # За замовчуванням валюта окладу = валюта компанії → курс 1.0
        slip = self._payslip()
        self.assertEqual(slip.salary_currency_id, self.company.currency_id)
        self.assertAlmostEqual(slip.salary_rate, 1.0, places=6)

    def test_company_currency_no_conversion(self):
        # Оклад 25000 у валюті компанії → нарахування без перерахунку
        slip = self._payslip()
        slip._generate_accruals()
        acc = self._salary_accrual(slip)
        self.assertAlmostEqual(acc.amount, 25000.0, places=2)

    def test_foreign_wage_converted(self):
        # Оклад 1000 USD за курсом 40 → 40000 грн
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})
        slip = self._payslip()
        self.assertEqual(slip.salary_currency_id, self.usd)
        slip.salary_rate = 40.0
        slip._generate_accruals()
        acc = self._salary_accrual(slip)
        self.assertAlmostEqual(acc.amount, 40000.0, places=2)

    def test_foreign_wage_taxes_in_uah(self):
        # Податки рахуються від гривневого еквіваленту (gross у грн)
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})
        slip = self._payslip()
        slip.salary_rate = 40.0
        slip.action_compute_sheet()
        self.assertAlmostEqual(slip.gross_salary, 40000.0, places=2)
        # Військовий збір 5% від гривневого gross = 2000 (без ПСП-знижок)
        self.assertAlmostEqual(slip.military_tax_amount, 2000.0, places=2)

    def test_foreign_prorated(self):
        # Половина місяця → половина гривневого окладу
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})
        slip = self._payslip()
        slip.salary_rate = 40.0
        slip.write({'worked_days': 10})
        slip._generate_accruals()
        acc = self._salary_accrual(slip)
        # 1000 × 40 × 10/20 = 20000
        self.assertAlmostEqual(acc.amount, 20000.0, places=2)

    def _payslip_for(self, date_from, date_to):
        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date_from,
            'date_to': date_to,
        })
        slip.write({
            'scheduled_hours': 160.0, 'scheduled_days': 20,
            'worked_days': 20, 'worked_hours': 160.0,
        })
        return slip

    def test_rate_comes_from_the_currency_table(self):
        """Курс береться з довідника, а не тільки з ручного поля.

        Решта тестів проставляють `salary_rate` руками, тож ланка «знайти
        курс на дату» лишалась непокритою — а саме вона працює в реальному
        розрахунку. Червень 2026: офіційний курс НБУ 44.2680.
        """
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})

        slip = self._payslip_for(date(2026, 6, 1), date(2026, 6, 30))

        self.assertAlmostEqual(slip.salary_rate, 44.2680, places=4)
        slip._generate_accruals()
        self.assertAlmostEqual(self._salary_accrual(slip).amount, 44268.0, places=2)

    def test_missing_rate_stops_the_payslip(self):
        """Місяць без курсу — це відмова, а не мовчазна виплата гривнями.

        `_convert` без запису курсу повертає 1.0, тож оклад 1000 USD пішов
        би у відомість як 1000 грн — помилка в сорок разів, і не на користь
        працівника. Жовтень 2026: курсу на цю дату в довіднику немає.
        """
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})
        self.env['res.currency.rate'].search([
            ('currency_id', '=', self.usd.id),
            ('name', '<=', '2026-10-31'),
        ]).unlink()

        slip = self._payslip_for(date(2026, 10, 1), date(2026, 10, 31))

        with self.assertRaises(UserError):
            slip._generate_accruals()

    def test_manual_rate_is_enough_without_the_table(self):
        """Курс, вписаний руками, — законний шлях, а не обхід перевірки.

        Повідомлення про відсутній курс радить саме це, тож перевірка не має
        відмовляти тому, хто пораду виконав.
        """
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})
        self.env['res.currency.rate'].search([
            ('currency_id', '=', self.usd.id),
            ('name', '<=', '2026-10-31'),
        ]).unlink()
        slip = self._payslip_for(date(2026, 10, 1), date(2026, 10, 31))

        slip.salary_rate = 45.0
        slip._generate_accruals()

        self.assertAlmostEqual(self._salary_accrual(slip).amount, 45000.0, places=2)

    def test_zeroed_rate_stops_the_payslip(self):
        """Нуль у курсі — стертий курс, а не «один до одного».

        Доти множення йшло через `salary_rate or 1.0`, тобто обнулений курс
        мовчки повертав ту саму одиницю, від якої цей PR і рятує.
        """
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})
        slip = self._payslip_for(date(2026, 6, 1), date(2026, 6, 30))

        slip.salary_rate = 0.0

        with self.assertRaises(UserError):
            slip._generate_accruals()

    def test_stale_rate_is_used_but_reported(self):
        """Курс, старший за період, не блокує розрахунок, але лишає слід.

        У довіднику законно тримати лише дати зміни, і курс з 1 числа чинний
        до кінця місяця. А от курс, старший за сам період, — це забутий
        довідник: рахувати за ним можна, мовчати про це не варто.
        """
        self.version.write({
            'salary_currency_id': self.usd.id, 'wage': 1000.0})
        self.env['res.currency.rate'].search([
            ('currency_id', '=', self.usd.id),
            ('name', '>', '2026-01-01'),
        ]).unlink()

        slip = self._payslip_for(date(2026, 7, 1), date(2026, 7, 31))

        with self.assertLogs('odoo.addons.l10n_ua_hr_salary.models.hr_payslip',
                             level='WARNING') as logged:
            slip._generate_accruals()

        self.assertTrue(any('2026-01-01' in line for line in logged.output),
                        f'у попередженні має бути дата застарілого курсу: {logged.output}')
        # Січневий курс — 42.3532, і саме за ним рахується липень.
        self.assertAlmostEqual(self._salary_accrual(slip).amount, 42353.2, places=1)
