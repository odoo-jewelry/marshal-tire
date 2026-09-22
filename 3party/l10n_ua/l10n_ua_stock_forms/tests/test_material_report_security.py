"""Whose report it is and which company it belongs to."""

from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests import tagged

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestMaterialReportSecurity(MaterialReportCase):
    """Who may see a report.

    Nothing in the ORM isolates transient records and nothing scopes them to
    a company; the rules in `security/material_report_security.xml` do both.
    These run as real users on purpose: record rules do not apply to the
    superuser the tests run as.
    """

    def test_a_report_is_visible_only_to_its_author(self):
        """Nothing in the ORM isolates transient records; the rule does."""
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()

        other = self.env['res.users'].create({
            'name': 'Other Storekeeper',
            'login': 'other.storekeeper',
            'group_ids': [(4, self.env.ref('stock.group_stock_user').id)],
        })
        Line = self.env['l10n_ua.material.report.line'].with_user(other)
        self.assertFalse(Line.search([('wizard_id', '=', wizard.id)]))

    def test_a_report_is_not_seen_from_another_company(self):
        """A report is a document of one company — its moves, its prices, its
        store. Being its author is therefore not enough to see it: change the
        company in the switcher and the previous company's numbers have to go
        off the screen, rather than stay there under the new company's name.

        Run as a real user: record rules do not apply to the superuser the
        tests run as, so this would pass on an empty security file otherwise.
        """
        other = self.env['res.company'].create({'name': 'Second Company'})
        keeper = self.env['res.users'].create({
            'name': 'Two-company Storekeeper',
            'login': 'two.company.storekeeper',
            'company_id': self.company.id,
            'company_ids': [(6, 0, [self.company.id, other.id])],
            'group_ids': [(4, self.env.ref('stock.group_stock_user').id)],
        })
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 4, 8, 0))
        wizard = self.env['l10n_ua.material.report.wizard'].with_user(
            keeper).create({
                'date_from': '2026-03-01',
                'date_to': '2026-03-31',
                'location_id': self.stock.id,
            })
        wizard.action_view_report()

        Wizard = self.env['l10n_ua.material.report.wizard'].with_user(keeper)
        Line = self.env['l10n_ua.material.report.line'].with_user(keeper)
        selected = {'allowed_company_ids': [self.company.id]}
        self.assertTrue(Wizard.with_context(**selected).search(
            [('id', '=', wizard.id)]))
        self.assertTrue(Line.with_context(**selected).search(
            [('wizard_id', '=', wizard.id)]))

        switched = {'allowed_company_ids': [other.id]}
        self.assertFalse(Wizard.with_context(**switched).search(
            [('id', '=', wizard.id)]))
        self.assertFalse(Line.with_context(**switched).search(
            [('wizard_id', '=', wizard.id)]))

    def test_printing_cannot_reach_another_author_rows(self):
        """The method is public, so an empty domain must not hand over
        everything that happens to be in the table."""
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 4, 8, 0))
        self._wizard().action_view_report()

        other = self.env['res.users'].create({
            'name': 'Curious Storekeeper',
            'login': 'curious.storekeeper',
            'group_ids': [(4, self.env.ref('stock.group_stock_user').id)],
        })
        with self.assertRaises(UserError):
            self.env['l10n_ua.material.report.line'].with_user(
                other).action_print_report([])

    def test_the_menu_builds_the_report_of_the_company_in_force(self):
        """The other half of following the switcher: what the menu builds is a
        report of the company selected and of a store of that company.

        No warehouse is created here — a company created while the tests run
        comes with one of its own (`res_company.py`, `create`). Which of its
        stores the report opens on is the default's business; what is asserted
        is that the store belongs to the company selected, and not to the one
        left behind.
        """
        other = self.env['res.company'].create({'name': 'Second Company'})

        action = self.env['l10n_ua.material.report.wizard'].with_company(
            other).with_context(
                allowed_company_ids=[other.id]).action_open_default_report()
        wizard = self.env['l10n_ua.material.report.wizard'].browse(
            action['context']['active_id'])

        self.assertEqual(wizard.company_id, other)
        self.assertEqual(wizard.location_id.company_id, other)
        self.assertNotEqual(wizard.location_id, self.stock)
