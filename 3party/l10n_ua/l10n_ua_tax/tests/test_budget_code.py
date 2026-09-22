"""Тест seed-даних КБКД військового збору (#171)."""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetCode(TransactionCase):

    VZ_CODES = ['11011000', '11011001', '11011600', '11011700', '11011800']

    def test_vz_budget_codes_seeded(self):
        codes = self.env['l10n_ua.budget.code'].search(
            [('tax_type', '=', 'vz')])
        found = set(codes.mapped('code'))
        for code in self.VZ_CODES:
            self.assertIn(code, found, 'КБКД %s не заведено' % code)
        # Усі мають непорожню назву.
        self.assertTrue(all(c.name for c in codes))

    def test_codes_unique(self):
        rec = self.env.ref('l10n_ua_tax.budget_code_vz_11011000')
        self.assertEqual(rec.code, '11011000')
        self.assertEqual(rec.tax_type, 'vz')
