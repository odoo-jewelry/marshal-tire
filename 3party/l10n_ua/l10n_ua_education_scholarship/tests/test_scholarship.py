"""Tests for l10n_ua_education_scholarship — payment lifecycle and computed totals."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_education_scholarship')
class TestScholarship(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.scholarship_type = cls.env.ref('l10n_ua_education_scholarship.scholarship_type_academic_basic')
        cls.kekv_2720 = cls.env['l10n_ua.kekv'].search([('code', '=', '2720')], limit=1)
        cls.year = cls.env['l10n_ua.education.academic.year'].create({
            'name': '2030/2031 SCHO',
            'year_start': 2030,
            'date_start': '2030-09-01',
            'date_end': '2031-06-30',
            'company_id': cls.env.company.id,
        })
        cls.partner1 = cls.env['res.partner'].create({'name': 'Студент 1', 'is_company': False})
        cls.partner2 = cls.env['res.partner'].create({'name': 'Студент 2', 'is_company': False})
        cls.member1 = cls.env['l10n_ua.education.contingent.member'].create({
            'partner_id': cls.partner1.id, 'member_type': 'student',
            'academic_year_id': cls.year.id, 'state': 'studying',
        })
        cls.member2 = cls.env['l10n_ua.education.contingent.member'].create({
            'partner_id': cls.partner2.id, 'member_type': 'student',
            'academic_year_id': cls.year.id, 'state': 'studying',
        })

    def test_create_with_sequence(self):
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2025,
            'period_month': '10',
        })
        self.assertNotEqual(payment.name, 'Нова')
        self.assertTrue(payment.name.startswith('СТП-'),
                         f"unexpected sequence: {payment.name}")

    def test_default_kekv_from_type(self):
        self.scholarship_type.default_kekv_id = self.kekv_2720
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2025, 'period_month': '11',
        })
        self.assertEqual(payment.kekv_id, self.kekv_2720)

    def _create_defaulted_line(self, scholarship_type, year, month):
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': scholarship_type.id,
            'period_year': year,
            'period_month': str(month),
        })
        return self.env['l10n_ua.scholarship.payment.line'].create({
            'payment_id': payment.id,
            'member_id': self.member1.id,
        })

    def test_higher_education_rate_changes_from_september_2026(self):
        self.env.company.l10n_ua_education_type = 'zvo_3_4'

        august = self._create_defaulted_line(
            self.scholarship_type, 2026, 8)
        september = self._create_defaulted_line(
            self.scholarship_type, 2026, 9)

        self.assertEqual(august.amount, 2000)
        self.assertEqual(september.amount, 4000)

    def test_pre_higher_advanced_rate_is_date_aware(self):
        self.env.company.l10n_ua_education_type = 'zvo_1_2'
        advanced = self.env.ref(
            'l10n_ua_education_scholarship.'
            'scholarship_type_academic_advanced')

        august = self._create_defaulted_line(advanced, 2026, 8)
        september = self._create_defaulted_line(advanced, 2026, 9)

        self.assertEqual(august.amount, 2197)
        self.assertEqual(september.amount, 4394)

    def test_professional_basic_rate_from_september_2026(self):
        self.env.company.l10n_ua_education_type = 'pto'

        september = self._create_defaulted_line(
            self.scholarship_type, 2026, 9)

        self.assertEqual(september.amount, 2500)

    def test_manual_amount_overrides_statutory_rate(self):
        self.env.company.l10n_ua_education_type = 'zvo_3_4'
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2026,
            'period_month': '9',
        })
        line = self.env['l10n_ua.scholarship.payment.line'].create({
            'payment_id': payment.id,
            'member_id': self.member1.id,
            'amount': 4500,
        })

        self.assertEqual(line.amount, 4500)

    def test_inline_line_gets_statutory_rate_before_insert(self):
        self.env.company.l10n_ua_education_type = 'zvo_3_4'

        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2026,
            'period_month': '9',
            'line_ids': [(0, 0, {'member_id': self.member1.id})],
        })

        self.assertEqual(payment.line_ids.amount, 4000)

    def test_fallback_amount_for_unmapped_institution(self):
        self.env.company.l10n_ua_education_type = 'other'
        self.scholarship_type.monthly_amount = 1234

        line = self._create_defaulted_line(
            self.scholarship_type, 2026, 9)

        self.assertEqual(line.amount, 1234)

    def test_incomplete_period_falls_back_to_default_amount(self):
        """Очищений «Рік» у формі не має валити розрахунок суми."""
        self.env.company.l10n_ua_education_type = 'zvo_3_4'
        self.scholarship_type.monthly_amount = 1500

        payment = self.env['l10n_ua.scholarship.payment'].new({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': False,
            'period_month': '9',
        })
        line = self.env['l10n_ua.scholarship.payment.line'].new({
            'payment_id': payment.id,
            'member_id': self.member1.id,
        })

        self.assertEqual(line.amount, 1500)

    def test_lifecycle(self):
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2025, 'period_month': '10',
            'line_ids': [
                (0, 0, {'member_id': self.member1.id, 'amount': 2000}),
                (0, 0, {'member_id': self.member2.id, 'amount': 2500}),
            ],
        })
        self.assertEqual(payment.state, 'draft')
        self.assertEqual(payment.total_amount, 4500)
        self.assertEqual(payment.line_count, 2)

        payment.action_approve()
        self.assertEqual(payment.state, 'approved')
        payment.action_pay()
        self.assertEqual(payment.state, 'paid')

    def test_cannot_approve_empty(self):
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2025, 'period_month': '10',
        })
        with self.assertRaises(UserError):
            payment.action_approve()

    def test_cannot_cancel_paid(self):
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2025, 'period_month': '10',
            'line_ids': [(0, 0, {'member_id': self.member1.id, 'amount': 1500})],
        })
        payment.action_approve()
        payment.action_pay()
        with self.assertRaises(UserError):
            payment.action_cancel()

    def test_no_duplicate_member_in_one_payment(self):
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2025, 'period_month': '10',
            'line_ids': [(0, 0, {'member_id': self.member1.id, 'amount': 1500})],
        })
        with self.assertRaises(Exception):
            self.env['l10n_ua.scholarship.payment.line'].create({
                'payment_id': payment.id,
                'member_id': self.member1.id,
                'amount': 2000,
            })

    def test_negative_amount_rejected(self):
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2025, 'period_month': '10',
        })
        with self.assertRaises(ValidationError):
            self.env['l10n_ua.scholarship.payment.line'].create({
                'payment_id': payment.id,
                'member_id': self.member1.id,
                'amount': -100,
            })

    def test_member_domain_only_active_students(self):
        """The member_id field on the line carries a domain restricting state."""
        member_field = self.env['l10n_ua.scholarship.payment.line']._fields['member_id']
        self.assertIn("'state', 'in'", member_field.domain)
        self.assertIn("studying", member_field.domain)

    def test_non_taxable_zero_tax(self):
        """Academic scholarships (`is_taxable_pdfo=False`) have zero tax."""
        # scholarship_type_academic_basic has is_taxable_pdfo=False by default
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2031, 'period_month': '10',
            'line_ids': [(0, 0, {'member_id': self.member1.id, 'amount': 2000})],
        })
        line = payment.line_ids
        self.assertEqual(line.amount_pdfo, 0)
        self.assertEqual(line.amount_vz, 0)
        self.assertEqual(line.amount_net, 2000)

    def test_taxable_scholarship_computes_pdfo_vz(self):
        """Taxable scholarships compute 18% PDFO + 5% military tax."""
        taxable_type = self.env['l10n_ua.scholarship.type'].create({
            'name': 'Премія', 'code': 'PRZ', 'kind': 'other',
            'is_taxable_pdfo': True,
        })
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': taxable_type.id,
            'period_year': 2031, 'period_month': '11',
            'pdfo_rate': 18.0, 'vz_rate': 5.0,
            'line_ids': [(0, 0, {'member_id': self.member1.id, 'amount': 1000})],
        })
        line = payment.line_ids
        self.assertAlmostEqual(line.amount_pdfo, 180.0, places=2)
        self.assertAlmostEqual(line.amount_vz, 50.0, places=2)
        self.assertAlmostEqual(line.amount_net, 770.0, places=2)
        self.assertAlmostEqual(payment.total_pdfo, 180.0, places=2)
        self.assertAlmostEqual(payment.total_vz, 50.0, places=2)
        self.assertAlmostEqual(payment.total_net, 770.0, places=2)

    def test_pay_without_journal_keeps_compatibility(self):
        """If journal_id is empty, action_pay just transitions state — backward compat."""
        payment = self.env['l10n_ua.scholarship.payment'].create({
            'scholarship_type_id': self.scholarship_type.id,
            'period_year': 2031, 'period_month': '12',
            'line_ids': [(0, 0, {'member_id': self.member1.id, 'amount': 1500})],
        })
        payment.action_approve()
        payment.action_pay()
        self.assertEqual(payment.state, 'paid')
        self.assertFalse(payment.account_move_id)
