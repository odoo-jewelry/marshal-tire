"""Аванс за валютним окладом — у гривні, а не числом із договору.

Найдорожче місце з усіх, де оклад читався напряму: аванс не рахується від
розрахункового листка, а береться відсотком від окладу — і йде живими
грошима на картку. Оклад 1000 USD давав аванс 500 грн замість 22 134.
"""
from datetime import date

from odoo.tests import tagged

from .common import SalaryTestCase


@tagged('post_install', '-at_install')
class TestAdvanceCurrency(SalaryTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref('base.USD')
        cls.env['res.currency.rate'].create([
            {'name': '2026-01-01', 'currency_id': cls.usd.id,
             'company_id': cls.company.id, 'inverse_company_rate': 42.3532},
            {'name': '2026-06-01', 'currency_id': cls.usd.id,
             'company_id': cls.company.id, 'inverse_company_rate': 44.2680},
        ])
        cls.version.write({'salary_currency_id': cls.usd.id, 'wage': 1000.0})

    def test_advance_converts_the_wage(self):
        advance = self.env['hr.salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2026, 6, 15),
            'wage_percent': 50.0,
        })

        # 1000 USD × 44.2680 × 50% = 22 134 грн; без перерахунку було б 500.
        self.assertAlmostEqual(advance.gross_amount, 22134.0, places=2)

    def test_advance_uses_the_rate_of_its_own_date(self):
        """Аванс січня і аванс червня рахуються за різними курсами."""
        january = self.env['hr.salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2026, 1, 20),
            'wage_percent': 50.0,
        })

        self.assertAlmostEqual(january.gross_amount, 21176.6, places=2)

    def test_moving_the_advance_recomputes_the_amount(self):
        """Перенесення авансу на інший місяць змінює й курс.

        `gross_amount` збережене, тож без `date` у залежностях у базі лишався
        б курс дня створення — а це живі гроші на картку.
        """
        advance = self.env['hr.salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2026, 6, 15),
            'wage_percent': 50.0,
        })
        self.assertAlmostEqual(advance.gross_amount, 22134.0, places=2)

        advance.date = date(2026, 1, 20)

        self.assertAlmostEqual(advance.gross_amount, 21176.6, places=2)

    def test_advance_run_converts_the_wage(self):
        """Пакетне нарахування має ту саму ваду й те саме лікування."""
        run = self.env['hr.salary.advance.run'].create({
            'name': 'Аванс 06/2026',
            'date': date(2026, 6, 15),
            'company_id': self.company.id,
        })

        self.assertAlmostEqual(
            run._get_employee_wage(self.employee), 44268.0, places=2)

    def test_run_skips_employees_without_a_rate_instead_of_dying(self):
        """Один працівник без курсу не має лишати без авансу всю установу.

        Пропущені не зникають мовчки: їхні імена йдуть у попередження, а
        повторний запуск підхопить їх, щойно курс внесуть.
        """
        # Період, на який курсу немає взагалі.
        run = self.env['hr.salary.advance.run'].create({
            'name': 'Аванс 12/2025',
            'date': date(2025, 12, 20),
            'company_id': self.company.id,
        })
        other = self.env['hr.employee'].create({
            'name': 'Гривневий працівник',
            'company_id': self.company.id,
        })
        other.current_version_id.write({
            'wage': 20000.0,
            'contract_date_start': date(2024, 1, 15),
        })

        result = run.action_generate_advances()

        self.assertEqual(result.get('tag'), 'display_notification',
                         'пропуск має бути видимим, а не тихим')
        self.assertIn(self.employee.name, result['params']['message'])
        paid = run.advance_ids.mapped('employee_id')
        self.assertIn(other, paid, 'решта працівників мають отримати аванс')
        self.assertNotIn(self.employee, paid)


@tagged('post_install', '-at_install')
class TestAllowanceCurrency(SalaryTestCase):
    """Надбавка у відсотках від валютного окладу — теж у гривні (#266)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref('base.USD')
        cls.env['res.currency.rate'].create([
            {'name': '2026-01-01', 'currency_id': cls.usd.id,
             'company_id': cls.company.id, 'inverse_company_rate': 42.3532},
            {'name': '2026-06-01', 'currency_id': cls.usd.id,
             'company_id': cls.company.id, 'inverse_company_rate': 44.2680},
        ])
        cls.allowance_type = cls.env['hr.allowance.type'].search([], limit=1) \
            or cls.env['hr.allowance.type'].create({'name': 'Надбавка (тест)'})

    def _allowance(self, method, **vals):
        return self.env['hr.version.allowance'].create({
            'version_id': self.version.id,
            'allowance_type_id': self.allowance_type.id,
            'calculation_method': method,
            **vals,
        })

    def test_percent_of_foreign_wage_is_converted(self):
        """10% від 1000 USD — це 4235 грн на січень, а не 100."""
        self.version.write({'salary_currency_id': self.usd.id, 'wage': 1000.0})

        allowance = self._allowance(
            'percent_salary', percent=10.0, date_from=date(2026, 1, 10))

        self.assertAlmostEqual(allowance.calculated_amount, 4235.32, places=2)
        self.assertNotAlmostEqual(allowance.calculated_amount, 100.0, places=2)

    def test_fixed_amount_is_left_alone(self):
        """Фіксована сума вводиться в гривні й перерахунку не потребує."""
        self.version.write({'salary_currency_id': self.usd.id, 'wage': 1000.0})

        allowance = self._allowance('fixed', amount=1500.0)

        self.assertAlmostEqual(allowance.calculated_amount, 1500.0, places=2)

    def test_payslip_takes_the_allowance_at_its_own_rate(self):
        """У листку надбавка йде за курсом періоду, а не датою її початку.

        Інакше в одному документі оклад рахувався б за курсом місяця, а
        надбавка до нього — за курсом позаминулого року.
        """
        self.version.write({'salary_currency_id': self.usd.id, 'wage': 1000.0})
        allowance = self._allowance(
            'percent_salary', percent=10.0, date_from=date(2026, 1, 10))
        self.assertAlmostEqual(allowance.calculated_amount, 4235.32, places=2)

        # Червневий курс вищий за січневий — сума в листку має це відбити.
        self.assertAlmostEqual(
            allowance._l10n_ua_amount_at(date(2026, 6, 30)), 4426.80, places=2)

    def test_manual_payslip_rate_reaches_the_allowance(self):
        """Курс, виправлений у листку, діє й на надбавку.

        `salary_rate` існує саме для ручного виправлення; якби надбавка
        шукала курс сама, оклад ішов би за виправленим курсом, а надбавка
        до нього — за довідниковим. А коли запису курсу немає взагалі й
        його вписано лише в листок, надбавка ще й падала б із помилкою
        там, де оклад порахувався.
        """
        self.version.write({'salary_currency_id': self.usd.id, 'wage': 1000.0})
        self._allowance('percent_salary', percent=10.0, date_from=date(2026, 1, 10))

        slip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'version_id': self.version.id,
            'date_from': date(2026, 6, 1),
            'date_to': date(2026, 6, 30),
        })
        slip.write({
            'scheduled_hours': 160.0, 'scheduled_days': 20,
            'worked_days': 20, 'worked_hours': 160.0,
        })
        slip.salary_rate = 50.0
        slip._generate_accruals()

        allowance_type = self.env['hr.accrual.type'].search(
            [('code', '=', 'ALLOWANCE')], limit=1)
        if not allowance_type:
            self.skipTest('немає типу нарахування ALLOWANCE')
        accrual = slip.accrual_ids.filtered(
            lambda a: a.accrual_type_id == allowance_type)
        # 1000 × 50 × 10% = 5000, а не 4235 за довідниковим курсом січня.
        self.assertAlmostEqual(accrual.amount, 5000.0, places=2)
