"""Tests for scheduled bank auto-sync — issue #189.

The cron method existed but no ir.cron record was shipped, and
sync_interval_hours was never honoured (nor was last_sync_date ever set).
These tests cover the shipped cron record and the per-config due logic.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBankAutoSync(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'bank'),
            ('company_id', '=', cls.company.id),
        ], limit=1) or cls.env['account.journal'].create({
            'name': 'Банк (тест)',
            'code': 'BNKT',
            'type': 'bank',
            'company_id': cls.company.id,
        })
        cls.Config = cls.env['l10n_ua.bank.sync.config']

    def _config(self, **vals):
        vals.setdefault('name', 'Sync тест')
        vals.setdefault('journal_id', self.journal.id)
        vals.setdefault('provider', 'manual')
        return self.Config.create(vals)

    def test_cron_record_exists(self):
        """A scheduled action must be shipped, running hourly."""
        cron = self.env.ref('l10n_ua_bank_sync.ir_cron_bank_auto_sync',
                            raise_if_not_found=False)
        self.assertTrue(cron, 'Auto-sync cron record must exist')
        self.assertEqual(cron.interval_type, 'hours')
        self.assertEqual(cron.interval_number, 1)
        self.assertIn('_cron_auto_sync', cron.code)

    def test_due_when_never_synced(self):
        cfg = self._config(auto_sync=True, sync_interval_hours=24)
        self.assertTrue(cfg._is_sync_due())

    def test_not_due_within_interval(self):
        now = fields.Datetime.now()
        cfg = self._config(auto_sync=True, sync_interval_hours=24)
        cfg.last_sync_date = now - timedelta(hours=5)
        self.assertFalse(cfg._is_sync_due(now))

    def test_due_after_interval(self):
        now = fields.Datetime.now()
        cfg = self._config(auto_sync=True, sync_interval_hours=24)
        cfg.last_sync_date = now - timedelta(hours=25)
        self.assertTrue(cfg._is_sync_due(now))

    def test_zero_interval_always_due(self):
        now = fields.Datetime.now()
        cfg = self._config(auto_sync=True, sync_interval_hours=0)
        cfg.last_sync_date = now
        self.assertTrue(cfg._is_sync_due(now))

    def test_cron_skips_configs_not_due(self):
        """A recently-synced config is skipped: no new job is created."""
        cfg = self._config(auto_sync=True, sync_interval_hours=24)
        cfg.last_sync_date = fields.Datetime.now()
        before = len(cfg.job_ids)
        self.Config._cron_auto_sync()
        self.assertEqual(len(cfg.job_ids), before,
                         'Config within its interval must not sync')
