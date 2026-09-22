"""Multi-company isolation for UA tax documents — issue #178.

Without record rules the tax documents were visible across ALL companies,
including non-UA ones. These tests assert the global multi-company rule scopes
each document to the user's allowed companies.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTaxMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Company = cls.env['res.company']
        cls.company_ua = Company.create({
            'name': 'UA Co (test)', 'country_id': cls.env.ref('base.ua').id})
        cls.company_other = Company.create({
            'name': 'Other Co (test)', 'country_id': cls.env.ref('base.fr').id})
        cls.doc_type = cls.env.ref('l10n_ua_tax.tax_document_type_ep_declaration')
        # user whose ONLY allowed company is the non-UA one
        cls.user_other = cls.env['res.users'].create({
            'name': 'Other User', 'login': 'ua_tax_other_user',
            'company_id': cls.company_other.id,
            'company_ids': [(6, 0, [cls.company_other.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('l10n_ua_account_base.group_ua_tax_accountant').id])],
        })

    def _document(self, company):
        return self.env['l10n_ua.tax.document'].create({
            'name': 'Test Document',
            'document_type_id': self.doc_type.id,
            'company_id': company.id,
        })

    def test_other_company_user_cannot_see_ua_document(self):
        """A user of the non-UA company must not see the UA company's document."""
        doc = self._document(self.company_ua)
        visible = self.env['l10n_ua.tax.document'].with_user(self.user_other).search([])
        self.assertNotIn(doc, visible)

    def test_same_company_user_sees_own_document(self):
        """The rule still lets a user see their own company's document."""
        doc = self._document(self.company_other)
        visible = self.env['l10n_ua.tax.document'].with_user(self.user_other).search([])
        self.assertIn(doc, visible)
