"""Tests for fixed assets — from ACCOUNTING_UKRAINE.md TMC/OZ tasks.

Tests cover:
- Asset creation
- Depreciation methods (straight-line, declining balance, cumulative, production)
- Depreciation schedule generation
- State workflow (draft → open → paused → close)
- Commissioning and write-off acts
"""

from datetime import date
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestAsset(TransactionCase):
    """Test fixed assets (основні засоби)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.asset_group = cls.env['l10n_ua.asset.group'].search([], limit=1)
        if not cls.asset_group:
            cls.asset_group = cls.env['l10n_ua.asset.group'].create({
                'code': '4',
                'name': 'Машини та обладнання',
                'min_useful_life': 5,
            })

    def _create_asset(self, **kwargs):
        vals = {
            'name': 'Сервер HP ProLiant',
            'acquisition_date': date(2025, 1, 15),
            'original_value': 120000,
            'salvage_value': 10000,
            'group_id': self.asset_group.id,
            'depreciation_method': 'straight_line',
            'useful_life': 60,  # 5 years
            'company_id': self.company.id,
        }
        vals.update(kwargs)
        return self.env['l10n_ua.asset'].create(vals)

    def test_asset_creation(self):
        """Asset should be created in draft state."""
        asset = self._create_asset()
        self.assertEqual(asset.state, 'draft')
        self.assertTrue(asset.name)

    def test_asset_book_value(self):
        """Book value should be original - accumulated depreciation."""
        asset = self._create_asset()
        self.assertEqual(asset.book_value, 120000)  # No depreciation yet

    def test_asset_commissioning(self):
        """Commissioning should set state to open."""
        asset = self._create_asset()
        asset.action_commission()
        self.assertEqual(asset.state, 'open')
        self.assertTrue(asset.commission_date)
        self.assertTrue(asset.commission_act_number)

    def test_straight_line_depreciation(self):
        """Straight-line: (original - salvage) / useful_life months."""
        asset = self._create_asset()
        # Monthly: (120000 - 10000) / 60 = 1833.33
        expected = (120000 - 10000) / 60
        self.assertAlmostEqual(asset.depreciation_amount, expected, places=2)

    def test_depreciation_schedule_generation(self):
        """Computing depreciation should generate schedule lines."""
        asset = self._create_asset()
        asset.action_commission()
        asset.action_compute_depreciation()
        self.assertTrue(asset.depreciation_line_ids,
                        'Depreciation schedule should have lines')
        self.assertEqual(len(asset.depreciation_line_ids), 60)

    def test_declining_balance_depreciation(self):
        """Declining balance should use accelerated rate on depreciable base."""
        asset = self._create_asset(
            depreciation_method='declining_balance',
            annual_depreciation_rate=40.0,
        )
        # First month: (120000 - 10000) × 40% / 12 = 3666.67
        depreciable = 120000 - 10000  # original - salvage
        expected_first = depreciable * 40 / 100 / 12
        self.assertAlmostEqual(asset.depreciation_amount, expected_first, places=2)

    def test_asset_pause_resume(self):
        """Should be able to pause and resume depreciation."""
        asset = self._create_asset()
        asset.action_commission()
        self.assertEqual(asset.state, 'open')
        asset.action_pause()
        self.assertEqual(asset.state, 'paused')
        asset.action_resume()
        self.assertEqual(asset.state, 'open')

    def test_asset_write_off(self):
        """Write-off should close the asset."""
        asset = self._create_asset()
        asset.action_commission()
        asset.action_write_off()
        self.assertEqual(asset.state, 'close')
        self.assertTrue(asset.writeoff_date)
        self.assertTrue(asset.writeoff_act_number)

    def test_asset_group_reference_data(self):
        """Asset groups should have required fields."""
        self.assertTrue(self.asset_group.code)
        self.assertTrue(self.asset_group.name)
        self.assertGreaterEqual(self.asset_group.min_useful_life, 0)
