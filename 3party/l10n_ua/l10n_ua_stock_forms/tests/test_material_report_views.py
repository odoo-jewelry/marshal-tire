"""The report on screen: the list, the pivot table and the period dialog."""

from datetime import date, datetime

import babel.dates
from lxml import etree

from odoo import fields
from odoo.exceptions import UserError
from odoo.models import READ_GROUP_DISPLAY_FORMAT
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from odoo.addons.l10n_ua_stock_forms.wizard.material_report_line import (
    STANDALONE_MONTH_FORMAT,
)

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestMaterialReportViews(MaterialReportCase):
    """The report on screen, and the action that opens it.
    """

    def test_view_report_materializes_the_printed_rows(self):
        self._move(self.supplier, self.stock, 100, datetime(2026, 2, 10, 8, 0))
        self._move(self.stock, self.customer, 30, datetime(2026, 3, 20, 8, 0))

        wizard = self._wizard()
        wizard.action_view_report()

        self.assertEqual(len(self._rows(wizard)), 1)
        line = self._rows(wizard)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.default_code, 'CEM400')
        self.assertEqual(line.opening_qty, 100)
        self.assertEqual(line.out_qty, 30)
        self.assertEqual(line.closing_qty, 70)
        self.assertEqual(line.closing_value, 70 * 150.0)
        self.assertEqual(line.uom_id, self.product.uom_id)
        self.assertEqual(line.location_id, self.stock)
        self.assertEqual(line.date_from, wizard.date_from)
        self.assertEqual(line.currency_id, self.company.currency_id)

    def test_report_opens_on_the_list_with_the_pivot_a_switch_away(self):
        """No stored display mode: the control panel switcher is right there."""
        wizard = self._wizard()
        action = wizard.action_view_report()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'l10n_ua.material.report.line')
        self.assertEqual([view_type for _id, view_type in action['views']],
                         ['list', 'pivot'])
        self.assertEqual(action['view_mode'], 'list,pivot')
        self.assertEqual(action['domain'], [('wizard_id', '=', wizard.id)])

    def test_the_search_panel_fields_are_filled(self):
        """The left-hand panel narrows on categ_id and location_id, so both
        must be stored on every row — and the place must be the row's own, not
        the store they share."""
        shelf = self._shelf('Shelf C')
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 4, 8, 0))
        self._move(self.stock, shelf, 2, datetime(2026, 3, 5, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        rows = self._rows(wizard)

        self.assertEqual(rows.categ_id, self.category)
        self.assertEqual(rows.location_id, self.stock | shelf)
        Line = self.env['l10n_ua.material.report.line']
        self.assertEqual(Line.search_count([
            ('wizard_id', '=', wizard.id), ('categ_id', '=', self.category.id),
            ('is_monthly', '=', False),
        ]), 2)
        self.assertEqual(Line.search_count([
            ('wizard_id', '=', wizard.id), ('location_id', '=', shelf.id),
            ('is_monthly', '=', False),
        ]), 1)

    def test_rerunning_replaces_its_own_rows(self):
        self._move(self.supplier, self.stock, 12, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        wizard.action_view_report()

        self.assertEqual(len(self._rows(wizard)), 1)
        self.assertEqual(self._rows(wizard).in_qty, 12)

    def test_menu_opens_the_list_without_asking_anything(self):
        """The menu shows the report itself: current month, main store."""
        wizards = self.env['l10n_ua.material.report.wizard']
        action = wizards.action_open_default_report()

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'],
                         'l10n_ua.material.report.line')
        self.assertEqual([view_type for _id, view_type in action['views']],
                         ['list', 'pivot'])

        wizard = wizards.browse(action['context']['active_id'])
        self.assertEqual(wizard.location_id, self.warehouse.lot_stock_id)
        today = fields.Date.context_today(wizard)
        self.assertEqual(wizard.date_from, today.replace(day=1))
        self.assertEqual(wizard.date_to, today)

    def test_the_period_picker_can_find_its_wizard(self):
        """The rows carry no link back, so the picker reads the wizard from
        the action context; without it the period could not be changed."""
        wizard = self._wizard()
        action = wizard.action_view_report()

        self.assertEqual(action['context']['active_id'], wizard.id)

    def test_the_report_reloaded_from_its_id_still_shows_one_report(self):
        """Coming back from a drilled-down list, the client reloads the action
        from the server by id: the URL keeps the id and `active_id`, never the
        domain the wizard put on the action. So the action record has to narrow
        to one report by itself, or the reader gets every row they ever
        produced — one per report they ran, all with the same numbers.

        Judged by what the domain selects rather than by how it is spelled:
        two reports of the same period exist here, and the restored one may
        show only its own rows."""
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 4, 8, 0))
        first = self._wizard()
        first.action_view_report()
        second = self._wizard()
        second.action_view_report()

        action = self.env['ir.actions.actions']._for_xml_id(
            'l10n_ua_stock_forms.action_material_report_lines')
        # What the client does with the string when it comes back: evaluate it
        # against the context, where `active_id` is the report being read.
        domain = safe_eval(action['domain'], {'active_id': second.id})
        rows = self.env['l10n_ua.material.report.line'].search(domain)

        self.assertEqual(rows.wizard_id, second)
        self.assertEqual(rows, second.line_ids)

    def test_the_period_dialog_opens_on_the_report_being_read(self):
        """The button hands the dialog the very record behind the rows."""
        wizard = self._wizard()
        action = wizard.action_open_period()

        self.assertEqual(action['target'], 'new')
        self.assertEqual(action['res_model'], 'l10n_ua.material.report.wizard')
        self.assertEqual(action['res_id'], wizard.id)

    def test_the_period_dialog_recomputes_the_report(self):
        """The period is a parameter, not a filter: the opening balance has to
        be re-read, not merely narrowed. The dialog writes the dates itself,
        the way a form does, and the button only rebuilds the rows."""
        self._move(self.supplier, self.stock, 60, datetime(2026, 2, 10, 8, 0))
        self._move(self.supplier, self.stock, 25, datetime(2026, 4, 6, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        self.assertFalse(self._rows(wizard).in_qty)

        wizard.write({'date_from': '2026-04-01', 'date_to': '2026-04-30'})
        self.assertEqual(wizard.action_apply_period()['type'],
                         'ir.actions.act_window_close')

        line = self._rows(wizard)
        self.assertEqual(line.in_qty, 25)
        # The February receipt is now an opening balance, not a receipt.
        self.assertEqual(line.opening_qty, 60)
        self.assertEqual(line.closing_qty, 85)

    def test_the_period_dialog_refuses_a_reversed_period(self):
        """The form saves before the button runs, so the constraint catches a
        reversed pair in the dialog and the report is never rebuilt from it."""
        wizard = self._wizard()
        with self.assertRaises(UserError):
            wizard.write({'date_from': '2026-04-30', 'date_to': '2026-04-01'})
        self.assertEqual(wizard.date_from, date(2026, 3, 1))

    def test_months_are_grouped_the_way_the_pivot_groups_them(self):
        """The pivot lays the months out by date_from:month — and takes the
        monthly rows only, otherwise the collapsed one would be counted with
        them a second time."""
        self._move(self.supplier, self.stock, 10, datetime(2026, 3, 4, 8, 0))
        self._move(self.supplier, self.stock, 6, datetime(2026, 4, 7, 8, 0))
        wizard = self._wizard(date_from='2026-03-01', date_to='2026-04-30')
        wizard.action_view_report()

        groups = self.env['l10n_ua.material.report.line']._read_group(
            [('wizard_id', '=', wizard.id), ('is_monthly', '=', True)],
            groupby=['date_from:month'],
            aggregates=['in_value:sum'],
        )
        self.assertEqual([values[1] for values in groups],
                         [10 * 150.0, 6 * 150.0])

    def test_the_pivot_measures_read_like_the_list(self):
        """One report shown two ways should not have to be relearned: every
        figure the list carries is a measure of the pivot, and in the same
        order — quantity then amount, for the opening balance, receipts, issues
        and the closing balance.

        The order of the columns is the order the measures are named in the
        arch (`_getMeasuresRow`, web/static/src/views/pivot/pivot_model.js), so
        that is what is checked, and against the list rather than against a
        literal: what matters is that the two agree.
        """
        figures = [
            'opening_qty', 'opening_value',
            'in_qty', 'in_value',
            'out_qty', 'out_value',
            'closing_qty', 'closing_value',
        ]
        arch = {
            view: etree.fromstring(self.env.ref(
                f'l10n_ua_stock_forms.view_material_report_line_{view}').arch)
            for view in ('list', 'pivot')
        }
        in_pivot = [node.get('name') for node in arch['pivot'].iter('field')
                    if node.get('type') == 'measure']
        in_list = [node.get('name') for node in arch['list'].iter('field')
                   if node.get('name') in figures]

        self.assertEqual(in_pivot, figures)
        self.assertEqual(in_list, in_pivot)

    def test_month_labels_use_the_nominative_case(self):
        """The month in a label stands on its own, so it needs the nominative.

        Both spellings are asked of babel rather than written out here: they
        are CLDR data, not terms of this module, and a literal would only
        restate what the library already knows. Asserting the label differs
        from the genitive is what actually pins the override down — spelling
        the expected string out would leave the test green even if the
        override were deleted in a language where the two forms coincide.
        """
        self._move(self.supplier, self.stock, 10, datetime(2026, 7, 4, 8, 0))
        wizard = self._wizard(date_from='2026-07-01', date_to='2026-07-31')
        wizard.action_view_report()

        groups = self.env['l10n_ua.material.report.line'].with_context(
            lang='uk_UA').formatted_read_group(
            [('wizard_id', '=', wizard.id), ('is_monthly', '=', True)],
            groupby=['date_from:month'],
        )
        label = groups[0]['date_from:month'][1]
        if not self.env['res.lang'].search_count([('code', '=', 'uk_UA')]):
            # Without Ukrainian in the database, check at least that a label exists.
            self.assertTrue(label)
            return

        july = date(2026, 7, 1)
        standalone = babel.dates.format_date(
            july, format=STANDALONE_MONTH_FORMAT, locale='uk_UA')
        in_a_date = babel.dates.format_date(
            july, format=READ_GROUP_DISPLAY_FORMAT['month'], locale='uk_UA')
        self.assertEqual(label, standalone)
        self.assertNotEqual(label, in_a_date)
