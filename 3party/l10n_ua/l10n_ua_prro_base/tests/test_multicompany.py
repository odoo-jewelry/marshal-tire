"""Multi-company isolation for PRRO records — issue #178.

Without record rules the PRRO configs (and their shifts/receipts) were visible
across ALL companies, including non-UA ones. These tests assert the global
multi-company rules scope each config to the user's allowed companies.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestPrroMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_ua = Company.create({
            'name': 'UA Co (test)', 'country_id': cls.env.ref('base.ua').id})
        cls.company_other = Company.create({
            'name': 'Other Co (test)', 'country_id': cls.env.ref('base.fr').id})
        # user whose ONLY allowed company is the non-UA one
        cls.user_other = cls.env['res.users'].create({
            'name': 'Other User', 'login': 'prro_other_user',
            'company_id': cls.company_other.id,
            'company_ids': [(6, 0, [cls.company_other.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('point_of_sale.group_pos_user').id])],
        })

    def _config(self, company):
        return self.env['l10n_ua.prro.config'].create({
            'name': 'PRRO %s' % company.name,
            'provider': 'checkbox',
            'company_id': company.id,
        })

    def test_other_company_user_cannot_see_ua_config(self):
        """A user of the non-UA company must not see the UA company's config."""
        cfg = self._config(self.company_ua)
        visible = self.env['l10n_ua.prro.config'].with_user(self.user_other).search([])
        self.assertNotIn(cfg, visible)

    def test_same_company_user_sees_own_config(self):
        """The rule still lets a user see their own company's config."""
        cfg = self._config(self.company_other)
        visible = self.env['l10n_ua.prro.config'].with_user(self.user_other).search([])
        self.assertIn(cfg, visible)
