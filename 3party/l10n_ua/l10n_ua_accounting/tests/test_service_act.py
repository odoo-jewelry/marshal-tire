"""Tests for service acts (Акти наданих послуг).

Tests cover:
- Creation and auto-sequencing
- State transitions (draft → confirmed → invoiced)
- Invoice generation
- Line totals computation
"""

from datetime import date
from odoo.tests import tagged
from odoo.exceptions import UserError
from .common import AccountingTestCase


@tagged('post_install', '-at_install')
class TestServiceAct(AccountingTestCase):
    """Test service acts (акти наданих послуг)."""

    def _create_service_act(self, **kwargs):
        """Helper to create a service act with a line."""
        vals = {
            'date': date.today(),
            'partner_id': self.partner.id,
            'line_ids': [(0, 0, {
                'name': 'Консультаційні послуги',
                'quantity': 10,
                'price_unit': 5000,
            })],
        }
        vals.update(kwargs)
        return self.env['l10n_ua.service.act'].create(vals)

    def test_service_act_creation(self):
        """Service act should be created in draft state with auto-sequence."""
        act = self._create_service_act()
        self.assertEqual(act.state, 'draft')
        self.assertTrue(act.name)

    def test_service_act_line_totals(self):
        """Line subtotal should be quantity × price_unit."""
        act = self._create_service_act()
        line = act.line_ids[0]
        self.assertEqual(line.price_subtotal, 50000)  # 10 × 5000

    def test_service_act_confirm(self):
        """Confirming should change state to confirmed."""
        act = self._create_service_act()
        act.action_confirm()
        self.assertEqual(act.state, 'confirmed')

    def test_service_act_draft_from_confirmed(self):
        """Should be able to go back to draft from confirmed."""
        act = self._create_service_act()
        act.action_confirm()
        act.action_draft()
        self.assertEqual(act.state, 'draft')

    def test_service_act_cancel(self):
        """Should be able to cancel a draft act."""
        act = self._create_service_act()
        act.action_cancel()
        self.assertEqual(act.state, 'cancelled')

    def test_service_act_create_invoice(self):
        """Creating invoice from confirmed act should generate account.move."""
        act = self._create_service_act()
        act.action_confirm()
        act.action_create_invoice()
        self.assertEqual(act.state, 'invoiced')
        self.assertTrue(act.invoice_id, 'Invoice should be created')
        self.assertEqual(act.invoice_id.move_type, 'out_invoice')

    def test_service_act_multiple_lines(self):
        """Act with multiple lines should compute totals correctly."""
        act = self.env['l10n_ua.service.act'].create({
            'date': date.today(),
            'partner_id': self.partner.id,
            'line_ids': [
                (0, 0, {'name': 'Послуга 1', 'quantity': 5, 'price_unit': 1000}),
                (0, 0, {'name': 'Послуга 2', 'quantity': 3, 'price_unit': 2000}),
            ],
        })
        self.assertEqual(act.amount_untaxed, 11000)  # 5000 + 6000
