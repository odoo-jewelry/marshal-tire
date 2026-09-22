"""The paper form: what goes on it and what the file is called."""

from datetime import datetime

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.safe_eval import safe_eval

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestMaterialReportPrinting(MaterialReportCase):
    """The printed form.

    What is printed is what is on screen, filters and all: the form is built
    from the materialized rows rather than recomputed.
    """

    def test_print_asks_nothing_and_prints_the_rows_on_screen(self):
        """No print dialog: the paper form is the rows already displayed."""
        self._move(self.supplier, self.stock, 3, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard(responsible_person='Storekeeper Ivanenko')
        wizard.action_view_report()

        lines = self.env['l10n_ua.material.report.line']
        action = lines.action_print_report([('wizard_id', '=', wizard.id)])

        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(
            action['report_name'], 'l10n_ua_stock_forms.report_material_report')
        # The wizard is printed so that the file can be named after it; the
        # rows that were on screen travel on the field.
        self.assertEqual(action['context']['active_ids'], wizard.ids)
        self.assertEqual(wizard.printed_line_ids, self._rows(wizard))

    def test_print_applies_the_filters_of_the_view(self):
        """The domain comes from the view, so narrowing the screen narrows
        the paper: printing must not quietly hand over everything."""
        shelf = self._shelf('Shelf D')
        self._move(self.supplier, self.stock, 11, datetime(2026, 3, 4, 8, 0))
        self._move(self.stock, shelf, 4, datetime(2026, 3, 5, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        self.assertEqual(len(self._rows(wizard)), 2)

        lines = self.env['l10n_ua.material.report.line']
        action = lines.action_print_report([
            ('wizard_id', '=', wizard.id),
            ('location_id', '=', shelf.id),
        ])

        printed = self._rows(wizard).filtered(lambda line: line.location_id == shelf)
        self.assertEqual(action['context']['active_ids'], wizard.ids)
        self.assertEqual(wizard.printed_line_ids, printed)

    def test_print_refuses_an_empty_selection(self):
        """Filters that match nothing leave nothing to print — say so rather
        than hand over an empty form."""
        wizard = self._wizard()
        wizard.action_view_report()

        with self.assertRaises(UserError):
            self.env['l10n_ua.material.report.line'].action_print_report([
                ('wizard_id', '=', wizard.id),
                ('closing_qty', '>', 10 ** 6),
            ])

    def test_printing_from_the_pivot_still_collapses_the_months(self):
        """The form is a summary of a period, wherever it is printed from."""
        self._move(self.supplier, self.stock, 6, datetime(2026, 3, 4, 8, 0))
        self._move(self.supplier, self.stock, 5, datetime(2026, 4, 7, 8, 0))
        wizard = self._wizard(date_from='2026-03-01', date_to='2026-04-30')
        wizard.action_view_report()

        # The pivot's domain: the monthly rows, two of them.
        lines = self.env['l10n_ua.material.report.line']
        action = lines.action_print_report([
            ('wizard_id', '=', wizard.id), ('is_monthly', '=', True),
        ])

        self.assertEqual(action['context']['active_ids'], wizard.ids)
        self.assertEqual(wizard.printed_line_ids, self._rows(wizard))
        self.assertEqual(len(wizard.printed_line_ids), 1)

    def test_printing_refuses_rows_of_several_reports(self):
        """One form describes one report: its header comes from the first row,
        so a mixed set would print the rest under a false heading."""
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 4, 8, 0))
        self._wizard().action_view_report()
        self._wizard(date_from='2026-03-01', date_to='2026-03-31').action_view_report()

        with self.assertRaises(UserError):
            self.env['l10n_ua.material.report.line'].action_print_report(
                [('is_monthly', '=', False)])

    def test_totals_of_the_form_describe_the_period(self):
        price = 150.0
        self._move(self.supplier, self.stock, 10, datetime(2026, 2, 10, 8, 0))
        self._move(self.supplier, self.stock, 6, datetime(2026, 3, 4, 8, 0))
        self._move(self.stock, self.customer, 4, datetime(2026, 4, 7, 8, 0))

        wizard = self._wizard(date_from='2026-03-01', date_to='2026-04-30')
        wizard.action_view_report()
        totals = self._rows(wizard)._report_totals()

        self.assertEqual(totals['opening_value'], 10 * price)
        self.assertEqual(totals['in_value'], 6 * price)
        self.assertEqual(totals['out_value'], 4 * price)
        self.assertEqual(totals['closing_value'], 12 * price)

    def test_the_form_signatures(self):
        """Signed twice; the accountant's name comes from the company when the
        HR localization is there, and the line stays blank when it is not."""
        self._move(self.supplier, self.stock, 3, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        rows = self._rows(wizard)

        signatures = rows._report_signatures()
        self.assertEqual(len(signatures), 2)
        # The person in charge hands it over: the name is already in the header.
        self.assertEqual(signatures[0]['title'], 'Handed over by')
        self.assertEqual(signatures[0]['role'], '')
        self.assertEqual(signatures[0]['name'], '')
        self.assertEqual(signatures[1]['title'], 'Accepted by')
        self.assertEqual(signatures[1]['role'], 'Accountant')

        if 'accountant_id' not in self.company._fields:
            self.assertEqual(signatures[1]['name'], '')
            return
        self.company.accountant_id = self.env['hr.employee'].create(
            {'name': 'Olha Bondarenko'})
        self.assertEqual(rows._report_signatures()[1]['name'], 'Olha Bondarenko')

    def test_the_form_names_the_category_only_when_there_is_one(self):
        """A narrowed report names its category; several cannot be named, and
        the header says "all" instead."""
        self._move(self.supplier, self.stock, 3, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        self.assertEqual(self._rows(wizard)._report_category_label(),
                         self.category.complete_name)

        diesel = self.env['product.product'].create({
            'name': 'Diesel Fuel',
            'is_storable': True,
            'standard_price': 50.0,
            'categ_id': self.env['product.category'].create({'name': 'Fuel'}).id,
        })
        self._move(self.supplier, self.stock, 7, datetime(2026, 3, 5, 8, 0),
                   product=diesel)
        wizard.action_view_report()

        self.assertEqual(len(self._rows(wizard).categ_id), 2)
        self.assertEqual(self._rows(wizard)._report_category_label(), 'all')

    def test_the_form_formats_numbers_for_the_reader_locale(self):
        """The form is a primary document: a Ukrainian accountant expects
        213 000,00, not 213000.00. The template must go through QWeb's own
        converter, which reads the separators from res.lang and the number of
        decimals from decimal.precision — neither of which the template is
        entitled to guess. Both are read here from the same sources, because
        they genuinely differ between databases (Product Unit is 4 digits on
        one of ours and 2 on another)."""
        self._move(self.supplier, self.stock, 1420, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        # The form is rendered the way the application renders it: of the
        # wizard, with the rows put on it by the print action.
        self.env['l10n_ua.material.report.line'].action_print_report(
            [('wizard_id', '=', wizard.id)])

        html = self.env['ir.actions.report']._render_qweb_html(
            'l10n_ua_stock_forms.report_material_report',
            wizard.ids,
        )[0].decode()

        lang = self.env['res.lang']._get_data(code=self.env.user.lang or 'en_US')
        digits = self.env['decimal.precision'].precision_get('Product Unit')
        expected = f'1{lang.thousands_sep}420{lang.decimal_point}{"0" * digits}'
        self.assertIn(expected, html)
        if lang.thousands_sep:
            # A relapse into "%.3f" would print the number unseparated.
            self.assertNotIn('1420', html)

    def test_the_report_prints_the_wizard_so_the_file_can_be_named(self):
        """Odoo names a downloaded file after the record only when a single one
        is printed, so the report is of the wizard and the rows ride along on a
        field. No binding either: it would print ticked rows straight from the
        client, past the collapsing and the checks."""
        report = self.env.ref(
            'l10n_ua_stock_forms.action_report_material_report')
        self.assertEqual(report.model, 'l10n_ua.material.report.wizard')
        self.assertFalse(report.binding_model_id)
        self.assertTrue(report.print_report_name)

    def test_the_file_is_named_after_the_store_and_the_period(self):
        """The expression is what the download controller evaluates, so it is
        exercised the same way rather than merely being present."""
        self._move(self.supplier, self.stock, 4, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        self.env['l10n_ua.material.report.line'].action_print_report(
            [('wizard_id', '=', wizard.id)])

        report = self.env.ref(
            'l10n_ua_stock_forms.action_report_material_report')
        name = safe_eval(report.print_report_name, {'object': wizard, 'time': None})

        self.assertIn('Material Report', name)
        self.assertIn('2026-03-01', name)
        self.assertIn('2026-03-31', name)
        # A slash in a store name would look like a folder in the file name.
        self.assertNotIn('/', name)
