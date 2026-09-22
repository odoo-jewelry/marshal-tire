"""Tests for the ПМД capitation recomputation on a contract line."""
from dateutil.relativedelta import relativedelta

from odoo.fields import Date
from odoo.tests import TransactionCase, tagged

from ..models.l10n_ua_medecin_nszu_contract import AGE_COEFFICIENTS


@tagged('post_install', '-at_install', 'l10n_ua_medecin_nszu')
class TestPmdCapitation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = Date.today()
        cls.package_pmd = cls.env.ref('l10n_ua_medecin_nszu.package_pmd_capitation_2025')
        cls.package_hosp = cls.env.ref('l10n_ua_medecin_nszu.package_hospital_2025')
        cls.doctor = cls.env['hr.employee'].create({'name': 'Лікар ПМД'})

    def _make_line(self, package):
        contract = self.env['l10n_ua.medecin.nszu.contract'].create({
            'date_start': '2025-01-01',
            'date_end': '2025-12-31',
        })
        return self.env['l10n_ua.medecin.nszu.contract.line'].create({
            'contract_id': contract.id,
            'package_id': package.id,
            'tariff': 1000.0,
        })

    def _make_patient(self, years=None, declared=True):
        """Пацієнт заданого віку; declared=False лишає його без активної декларації."""
        partner = self.env['res.partner'].create({'name': f'Пацієнт {years}'})
        patient = self.env['l10n_ua.medecin.patient'].create({
            'partner_id': partner.id,
            'company_id': self.env.company.id,
            # місяць запасу, щоб тест не ламався на межі дня народження
            'birthdate': self.today - relativedelta(years=years, months=1) if years else False,
        })
        if declared:
            declaration = self.env['l10n_ua.medecin.declaration'].create({
                'patient_id': patient.id,
                'doctor_id': self.doctor.id,
                'date_start': self.today,
            })
            declaration.action_activate()
        return patient

    def test_weighted_count_by_age_category(self):
        """Кожна вікова категорія множиться на свій коефіцієнт, а не рахується поштучно."""
        self._make_patient(3)     # 0_5   -> 4.0
        self._make_patient(3)     # 0_5   -> 4.0
        self._make_patient(10)    # 6_17  -> 2.2
        self._make_patient(30)    # 18_39 -> 1.0
        self._make_patient(50)    # 40_64 -> 1.2
        self._make_patient(70)    # 65+   -> 2.5
        expected = round(2 * AGE_COEFFICIENTS['0_5']
                          + AGE_COEFFICIENTS['6_17']
                          + AGE_COEFFICIENTS['18_39']
                          + AGE_COEFFICIENTS['40_64']
                          + AGE_COEFFICIENTS['65+'])

        line = self._make_line(self.package_pmd)
        line.action_compute_pmd_capitation()

        self.assertEqual(line.expected_units, expected)
        # Проста кількість пацієнтів дала б 6 — саме цю помилку тест і стереже.
        self.assertNotEqual(line.expected_units, 6)
        self.assertEqual(line.expected_amount, expected * 1000.0)

    def test_ignores_patients_without_active_declaration(self):
        """Пацієнт без чинної декларації не оплачується НСЗУ і в базу не входить."""
        self._make_patient(30)
        self._make_patient(30, declared=False)

        line = self._make_line(self.package_pmd)
        line.action_compute_pmd_capitation()

        self.assertEqual(line.expected_units, round(AGE_COEFFICIENTS['18_39']))

    def test_noop_for_non_capitation_package(self):
        """Кнопка мовчки нічого не робить на пакетах з іншою моделлю оплати."""
        self._make_patient(3)
        line = self._make_line(self.package_hosp)
        line.expected_units = 42

        line.action_compute_pmd_capitation()

        self.assertEqual(line.expected_units, 42)

    def test_no_declared_patients_gives_zero(self):
        line = self._make_line(self.package_pmd)
        line.expected_units = 99

        line.action_compute_pmd_capitation()

        self.assertEqual(line.expected_units, 0)

    def test_patient_without_birthdate_is_not_counted_as_adult(self):
        """Без дати народження вікової категорії немає — коефіцієнт не вгадуємо.

        Раніше `.get(category, 1.0)` мовчки зараховував таку декларацію як
        18–39. Для капітації це гроші НСЗУ за пацієнта, якого не можна
        віднести до жодної групи.
        """
        self._make_patient(30)
        self._make_patient(None)

        line = self._make_line(self.package_pmd)
        line.action_compute_pmd_capitation()

        self.assertEqual(line.expected_units, round(AGE_COEFFICIENTS['18_39']))

    def test_stale_age_category_is_refreshed_by_cron(self):
        """Пацієнти старішають без жодної події — категорію оновлює крон.

        `age_category` збережене й рахується від сьогоднішньої дати, тож без
        перерахунку дитина назавжди лишається в тій групі, у якій її завели:
        база капітації тримала б коефіцієнт 4.0 замість 2.2.
        """
        patient = self._make_patient(3)
        self.assertEqual(patient.age_category, '0_5')
        # Заднім числом «дорослішаємо» пацієнта в обхід compute — саме так це
        # виглядає в базі, де запис лежить із минулого року.
        self.env.cr.execute(
            "UPDATE l10n_ua_medecin_patient SET birthdate = %s WHERE id = %s",
            (self.today - relativedelta(years=10), patient.id))
        patient.invalidate_recordset(['birthdate', 'age_category'])
        self.assertEqual(patient.age_category, '0_5', 'збережена категорія застаріла')

        self.env['l10n_ua.medecin.patient']._cron_refresh_age_category()

        self.assertEqual(patient.age_category, '6_17')

        line = self._make_line(self.package_pmd)
        line.action_compute_pmd_capitation()

        self.assertEqual(line.expected_units, round(AGE_COEFFICIENTS['6_17']))
