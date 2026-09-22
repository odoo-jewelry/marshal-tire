"""Tests for НСЗУ contracts + packages."""
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_medecin_nszu')
class TestNszuContract(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.package_pmd = cls.env.ref('l10n_ua_medecin_nszu.package_pmd_capitation_2025')
        cls.package_hosp = cls.env.ref('l10n_ua_medecin_nszu.package_hospital_2025')

    def _make_contract(self, **kwargs):
        defaults = {
            'date_start': '2025-01-01',
            'date_end': '2025-12-31',
        }
        defaults.update(kwargs)
        return self.env['l10n_ua.medecin.nszu.contract'].create(defaults)

    def test_auto_sequence_name(self):
        c = self._make_contract()
        self.assertTrue(c.name.startswith('НСЗУ-'),
                         f"unexpected name: {c.name}")

    def test_lifecycle(self):
        c = self._make_contract()
        # Add a line
        self.env['l10n_ua.medecin.nszu.contract.line'].create({
            'contract_id': c.id,
            'package_id': self.package_pmd.id,
            'tariff': 878.0,
            'expected_units': 1000,
        })
        self.assertEqual(c.state, 'draft')
        self.assertEqual(c.total_expected, 878_000.0)

        c.action_submit()
        self.assertEqual(c.state, 'submitted')
        c.action_activate()
        self.assertEqual(c.state, 'active')
        c.action_expire()
        self.assertEqual(c.state, 'expired')

    def test_cannot_submit_empty(self):
        c = self._make_contract()
        with self.assertRaises(UserError):
            c.action_submit()

    def test_terminate_from_active(self):
        c = self._make_contract()
        self.env['l10n_ua.medecin.nszu.contract.line'].create({
            'contract_id': c.id,
            'package_id': self.package_hosp.id,
            'tariff': 5000.0,
            'expected_units': 100,
        })
        c.action_submit()
        c.action_activate()
        c.action_terminate()
        self.assertEqual(c.state, 'terminated')

    def test_expected_amount_compute(self):
        c = self._make_contract()
        line = self.env['l10n_ua.medecin.nszu.contract.line'].create({
            'contract_id': c.id,
            'package_id': self.package_pmd.id,
            'tariff': 1000.0,
            'expected_units': 50,
        })
        self.assertEqual(line.expected_amount, 50_000.0)
        line.expected_units = 100
        self.assertEqual(line.expected_amount, 100_000.0)
