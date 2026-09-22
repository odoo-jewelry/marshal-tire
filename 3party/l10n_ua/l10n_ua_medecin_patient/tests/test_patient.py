"""Tests for patient + declaration models."""
from datetime import date, timedelta
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_medecin_patient')
class TestMedecinPatient(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Іванов Іван', 'is_company': False})
        cls.partner2 = cls.env['res.partner'].create({'name': 'Петрова Марія', 'is_company': False})
        cls.doctor = cls.env['hr.employee'].create({'name': 'Лікар Сергій'})
        cls.doctor2 = cls.env['hr.employee'].create({'name': 'Лікар Олена'})

    def test_age_category_compute(self):
        Patient = self.env['l10n_ua.medecin.patient']
        cases = [
            (date.today() - timedelta(days=365 * 3), '0_5'),
            (date.today() - timedelta(days=365 * 10), '6_17'),
            (date.today() - timedelta(days=365 * 30), '18_39'),
            (date.today() - timedelta(days=365 * 50), '40_64'),
            (date.today() - timedelta(days=365 * 70), '65+'),
        ]
        for bd, expected in cases:
            p = Patient.create({
                'partner_id': self.partner.id, 'birthdate': bd,
            })
            self.assertEqual(p.age_category, expected, f"birthdate={bd}")
            p.unlink()  # avoid uniqueness clashes

    def test_rnokpp_validation(self):
        Patient = self.env['l10n_ua.medecin.patient']
        with self.assertRaises(ValidationError):
            Patient.create({'partner_id': self.partner.id, 'rnokpp': '123'})  # too short
        with self.assertRaises(ValidationError):
            Patient.create({'partner_id': self.partner.id, 'rnokpp': '12345abc90'})  # non-digit

    def test_unique_card_per_company(self):
        Patient = self.env['l10n_ua.medecin.patient']
        Patient.create({
            'partner_id': self.partner.id, 'patient_card_no': 'CARD-001',
        })
        with self.assertRaises(Exception):
            Patient.create({
                'partner_id': self.partner2.id, 'patient_card_no': 'CARD-001',
            })

    def test_declaration_activation_terminates_previous(self):
        """Активація нової декларації автоматично припиняє попередню активну для того ж пацієнта."""
        Patient = self.env['l10n_ua.medecin.patient']
        Decl = self.env['l10n_ua.medecin.declaration']
        patient = Patient.create({'partner_id': self.partner.id})

        d1 = Decl.create({
            'patient_id': patient.id, 'doctor_id': self.doctor.id,
            'date_signed': '2025-01-15',
        })
        d1.action_activate()
        self.assertEqual(d1.state, 'active')
        self.assertEqual(patient.active_declaration_id, d1)

        d2 = Decl.create({
            'patient_id': patient.id, 'doctor_id': self.doctor2.id,
            'date_signed': '2025-06-01',
        })
        d2.action_activate()
        d1.invalidate_recordset()
        patient.invalidate_recordset()
        self.assertEqual(d1.state, 'terminated')
        self.assertEqual(d2.state, 'active')
        self.assertEqual(patient.active_declaration_id, d2)
        self.assertEqual(patient.active_doctor_id, self.doctor2)

    def test_declaration_terminate_requires_reason(self):
        Patient = self.env['l10n_ua.medecin.patient']
        Decl = self.env['l10n_ua.medecin.declaration']
        patient = Patient.create({'partner_id': self.partner.id})
        d = Decl.create({
            'patient_id': patient.id, 'doctor_id': self.doctor.id,
        })
        d.action_activate()
        with self.assertRaises(UserError):
            d.action_terminate()  # no reason
        d.termination_reason = 'patient_choice'
        d.action_terminate()
        self.assertEqual(d.state, 'terminated')

    def test_declaration_dates_validation(self):
        Patient = self.env['l10n_ua.medecin.patient']
        Decl = self.env['l10n_ua.medecin.declaration']
        patient = Patient.create({'partner_id': self.partner.id})
        with self.assertRaises(ValidationError):
            Decl.create({
                'patient_id': patient.id, 'doctor_id': self.doctor.id,
                'date_start': '2025-06-01', 'date_terminated': '2025-05-01',
            })
