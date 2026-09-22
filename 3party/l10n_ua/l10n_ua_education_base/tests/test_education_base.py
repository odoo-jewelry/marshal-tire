"""Tests for l10n_ua_education_base — academic year, groups, contingent lifecycle."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_education_base')
class TestEducationBase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Іван Петренко (Тест)', 'is_company': False,
        })
        cls.partner2 = cls.env['res.partner'].create({
            'name': 'Марія Коваленко (Тест)', 'is_company': False,
        })
        # Always create a fresh academic year for tests (so we don't fight the seed record)
        cls.year = cls.env['l10n_ua.education.academic.year'].create({
            'name': '2024/2025 TEST',
            'year_start': 2024,
            'date_start': '2024-09-01',
            'date_end': '2025-06-30',
            'company_id': cls.company.id,
        })

    def test_academic_year_compute_year_end(self):
        self.assertEqual(self.year.year_end, 2025)

    def test_academic_year_invalid_dates(self):
        Year = self.env['l10n_ua.education.academic.year']
        with self.assertRaises(ValidationError):
            Year.create({
                'name': '2030/2031 BAD',
                'year_start': 2030,
                'date_start': '2030-09-01',
                'date_end': '2030-06-30',  # earlier than start
                'company_id': self.company.id,
            })

    def test_only_one_active_year(self):
        self.year.is_active = True
        Year = self.env['l10n_ua.education.academic.year']
        with self.assertRaises(ValidationError):
            Year.create({
                'name': '2026/2027 DUP',
                'year_start': 2026,
                'date_start': '2026-09-01',
                'date_end': '2027-06-30',
                'company_id': self.company.id,
                'is_active': True,  # already one active for this company
            })

    def test_group_default_year_from_active(self):
        self.year.is_active = True
        grp = self.env['l10n_ua.education.group'].create({
            'name': '3-А (test)', 'group_type': 'class', 'level': 3,
        })
        self.assertEqual(grp.academic_year_id, self.year)
        self.assertEqual(grp.company_id, self.company)

    def test_contingent_lifecycle_happy_path(self):
        grp = self.env['l10n_ua.education.group'].create({
            'name': 'PHYS-21-1', 'group_type': 'course_group', 'level': 1,
            'academic_year_id': self.year.id,
        })
        member = self.env['l10n_ua.education.contingent.member'].create({
            'partner_id': self.partner.id,
            'member_type': 'student',
            'academic_year_id': self.year.id,
            'group_id': grp.id,
            'student_number': 'PHYS-001',
            'date_application': '2024-07-15',
        })
        self.assertEqual(member.state, 'applicant')

        member.action_enroll()
        self.assertEqual(member.state, 'enrolled')
        self.assertTrue(member.date_enrolled)

        member.action_start_studying()
        self.assertEqual(member.state, 'studying')

        member.action_take_leave()
        self.assertEqual(member.state, 'on_leave')

        member.action_return_from_leave()
        self.assertEqual(member.state, 'studying')

        member.action_graduate()
        self.assertEqual(member.state, 'graduated')
        self.assertTrue(member.date_graduated)

    def test_contingent_cannot_skip_states(self):
        member = self.env['l10n_ua.education.contingent.member'].create({
            'partner_id': self.partner2.id,
            'member_type': 'pupil',
            'academic_year_id': self.year.id,
        })
        # applicant -> graduated direct must fail
        with self.assertRaises(UserError):
            member.action_graduate()

    def test_contingent_expel_from_applicant(self):
        """A failed applicant can be directly expelled (not enrolled)."""
        member = self.env['l10n_ua.education.contingent.member'].create({
            'partner_id': self.partner.id,
            'member_type': 'pupil',
            'academic_year_id': self.year.id,
        })
        member.action_expel()
        self.assertEqual(member.state, 'expelled')

    def test_group_year_mismatch_blocks(self):
        other_year = self.env['l10n_ua.education.academic.year'].create({
            'name': '2026/2027 OTHER',
            'year_start': 2026,
            'date_start': '2026-09-01',
            'date_end': '2027-06-30',
            'company_id': self.company.id,
        })
        grp = self.env['l10n_ua.education.group'].create({
            'name': 'OTHER-1', 'group_type': 'class', 'level': 5,
            'academic_year_id': other_year.id,
        })
        with self.assertRaises(ValidationError):
            self.env['l10n_ua.education.contingent.member'].create({
                'partner_id': self.partner.id,
                'member_type': 'pupil',
                'academic_year_id': self.year.id,  # different year
                'group_id': grp.id,
            })

    def test_company_education_fields(self):
        self.company.write({
            'l10n_ua_education_type': 'zzso',
            'l10n_ua_education_is_state': True,
            'l10n_ua_education_iea_code': 'ABC-12345',
        })
        self.assertEqual(self.company.l10n_ua_education_type, 'zzso')

    def test_student_number_unique_per_company(self):
        self.env['l10n_ua.education.contingent.member'].create({
            'partner_id': self.partner.id,
            'member_type': 'pupil',
            'academic_year_id': self.year.id,
            'student_number': 'UNIQ-001',
        })
        with self.assertRaises(Exception):
            self.env['l10n_ua.education.contingent.member'].create({
                'partner_id': self.partner2.id,
                'member_type': 'pupil',
                'academic_year_id': self.year.id,
                'student_number': 'UNIQ-001',  # duplicate
            })

    def test_group_member_count(self):
        grp = self.env['l10n_ua.education.group'].create({
            'name': 'COUNTER-1', 'group_type': 'class', 'level': 5,
            'academic_year_id': self.year.id,
        })
        m1 = self.env['l10n_ua.education.contingent.member'].create({
            'partner_id': self.partner.id, 'member_type': 'pupil',
            'academic_year_id': self.year.id, 'group_id': grp.id,
        })
        m2 = self.env['l10n_ua.education.contingent.member'].create({
            'partner_id': self.partner2.id, 'member_type': 'pupil',
            'academic_year_id': self.year.id, 'group_id': grp.id,
        })
        m1.action_enroll()
        m2.action_enroll()
        m2.action_start_studying()
        grp.invalidate_recordset(['member_count'])
        self.assertEqual(grp.member_count, 2)
        # Expel one and the count drops to 1
        m1.action_expel()
        grp.invalidate_recordset(['member_count'])
        self.assertEqual(grp.member_count, 1)
