"""Multi-company isolation test for hr.certificate.type (issue #178).

Verifies that the global ir.rule scopes hr.certificate.type records to the
user's allowed companies: a user restricted to a non-UA company must not see
records belonging to a UA company, but must see records of their own company.
"""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestCertificateTypeMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company_ua = cls.env['res.company'].create({
            'name': 'UA Test Co',
            'country_id': cls.env.ref('base.ua').id,
        })
        cls.company_other = cls.env['res.company'].create({
            'name': 'Non-UA Test Co',
            'country_id': cls.env.ref('base.us').id,
        })

        CertType = cls.env['hr.certificate.type']
        cls.type_ua = CertType.create({
            'name': 'UA cert type',
            'code': 'UA_MC',
            'company_id': cls.company_ua.id,
        })
        cls.type_other = CertType.create({
            'name': 'Other cert type',
            'code': 'OTHER_MC',
            'company_id': cls.company_other.id,
        })

        # User restricted to the non-UA company, with HR read access
        # (hr.group_hr_user grants read on hr.certificate.type per
        # security/ir.model.access.csv).
        cls.user = cls.env['res.users'].create({
            'name': 'Non-UA HR User',
            'login': 'nonua_hr_user_mc',
            'company_id': cls.company_other.id,
            'company_ids': [(6, 0, [cls.company_other.id])],
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.env.ref('hr.group_hr_user').id,
            ])],
        })

    def test_cannot_see_other_company_records(self):
        CertType = self.env['hr.certificate.type'].with_user(self.user)

        visible = CertType.search([
            ('id', 'in', [self.type_ua.id, self.type_other.id]),
        ])

        self.assertIn(
            self.type_other, visible,
            "User must see hr.certificate.type of their own company",
        )
        self.assertNotIn(
            self.type_ua, visible,
            "User must NOT see hr.certificate.type of another company",
        )
