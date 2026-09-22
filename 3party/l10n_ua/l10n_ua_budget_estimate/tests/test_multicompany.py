"""Multi-company isolation for budget estimates — issue #178."""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestBudgetEstimateMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_ua = Company.create({
            'name': 'UA Budget (test)', 'country_id': cls.env.ref('base.ua').id})
        cls.company_other = Company.create({
            'name': 'Other Budget (test)', 'country_id': cls.env.ref('base.fr').id})
        cls.user_other = cls.env['res.users'].create({
            'name': 'Other Budget User', 'login': 'budget_other_user',
            'company_id': cls.company_other.id,
            'company_ids': [(6, 0, [cls.company_other.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('l10n_ua_budget_base.group_ua_budget_user').id])],
        })

    def _estimate(self, company):
        return self.env['l10n_ua.budget.estimate'].create({'company_id': company.id})

    def test_other_company_user_cannot_see_ua_estimate(self):
        est = self._estimate(self.company_ua)
        visible = self.env['l10n_ua.budget.estimate'].with_user(self.user_other).search([])
        self.assertNotIn(est, visible)

    def test_same_company_user_sees_own_estimate(self):
        est = self._estimate(self.company_other)
        visible = self.env['l10n_ua.budget.estimate'].with_user(self.user_other).search([])
        self.assertIn(est, visible)
