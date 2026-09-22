"""The way down from a figure of the report to the movements behind it."""

from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.tests import tagged

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestMaterialReportMovements(MaterialReportCase):
    """From a figure down to the movements it was made of.

    A cell of the pivot table leads to the movements of its own measure, a
    row of the list to everything that moved through it.
    """

    def _movements_of(self, lines, measure, **context):
        """The action a click on a cell produces, and what it opens."""
        action = self.env['l10n_ua.material.report.line'].with_context(
            **context).action_open_movements([('id', 'in', lines.ids)], measure)
        found = self.env['stock.move.line'].search(action['domain'])
        return action, found

    def test_a_receipts_cell_opens_the_movements_behind_it(self):
        """What is under a cell must add up to the number on it, or the list
        below explains nothing."""
        receipt = self._move(self.supplier, self.stock, 40,
                             datetime(2026, 3, 5, 8, 0))
        self._move(self.stock, self.customer, 12, datetime(2026, 3, 20, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        row = self._rows(wizard, monthly=True)

        action, found = self._movements_of(row, 'in_value')

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'stock.move.line')
        # The client reads `views` and never `view_mode`: an action that comes
        # from `call_kw` is not run through `clean_action`, so nothing fills
        # the key in on the way and its absence breaks the client outright.
        self.assertEqual([view_type for _id, view_type in action['views']],
                         ['list', 'form'])
        self.assertEqual(found, receipt.move_line_ids)
        self.assertEqual(sum(found.mapped('quantity')), row.in_qty)

    def test_an_issues_cell_opens_the_movements_behind_it(self):
        """The other end of the same rows: what left the place, not what came."""
        self._move(self.supplier, self.stock, 40, datetime(2026, 3, 5, 8, 0))
        issue = self._move(self.stock, self.customer, 12,
                           datetime(2026, 3, 20, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        row = self._rows(wizard, monthly=True)

        _action, found = self._movements_of(row, 'out_qty')

        self.assertEqual(found, issue.move_line_ids)
        self.assertEqual(sum(found.mapped('quantity')), row.out_qty)

    def test_an_internal_transfer_is_seen_from_both_places(self):
        """One move line, two rows: it left one place and reached another, so
        it must show up as an issue of the first and a receipt of the second."""
        shelf = self._shelf('Shelf E')
        self._move(self.supplier, self.stock, 30, datetime(2026, 3, 3, 8, 0))
        transfer = self._move(self.stock, shelf, 12, datetime(2026, 3, 6, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        rows = self._rows(wizard, monthly=True)
        of_shelf = rows.filtered(lambda line: line.location_id == shelf)
        of_store = rows.filtered(lambda line: line.location_id == self.stock)

        _action, into_shelf = self._movements_of(of_shelf, 'in_qty')
        _action, out_of_store = self._movements_of(of_store, 'out_qty')

        self.assertEqual(into_shelf, transfer.move_line_ids)
        self.assertEqual(out_of_store, transfer.move_line_ids)

    def test_a_cell_lists_the_movements_of_its_own_month_only(self):
        """The month is a column of the table, so a cell is one month: April's
        receipts have no business under March."""
        march = self._move(self.supplier, self.stock, 5,
                           datetime(2026, 3, 4, 8, 0))
        april = self._move(self.supplier, self.stock, 9,
                           datetime(2026, 4, 4, 8, 0))
        wizard = self._wizard(date_from='2026-03-01', date_to='2026-04-30')
        wizard.action_view_report()
        row = self._rows(wizard, monthly=True).filtered(
            lambda line: line.date_from == date(2026, 3, 1))

        _action, found = self._movements_of(row, 'in_qty')

        self.assertEqual(found, march.move_line_ids)
        self.assertNotIn(april.move_line_ids, found)

    def test_a_cell_is_cut_on_the_reader_midnight(self):
        """The bounds are the report's own, zone and all: a move at 00:30 on
        1 April in Kyiv is April's, however UTC dates it."""
        evening = self._move(self.supplier, self.stock, 6,
                             datetime(2026, 3, 31, 20, 30))
        past_midnight = self._move(self.supplier, self.stock, 8,
                                   datetime(2026, 3, 31, 21, 30))
        wizard = self._kyiv(self._wizard(date_from='2026-03-01',
                                         date_to='2026-04-30'))
        wizard.action_view_report()
        row = self._rows(wizard, monthly=True).filtered(
            lambda line: line.date_from == date(2026, 3, 1))

        _action, found = self._movements_of(row, 'in_qty', tz='Europe/Kyiv')

        self.assertEqual(found, evening.move_line_ids)
        self.assertNotIn(past_midnight.move_line_ids, found)
        self.assertEqual(sum(found.mapped('quantity')), row.in_qty)

    def test_a_balance_cell_says_why_it_has_no_movements(self):
        """A balance is a state at a moment: the movements behind it start
        before the report and its amount is a price, not a sum of documents. A
        plausible list that does not add up would be worse than a word."""
        self._move(self.supplier, self.stock, 7, datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        row = self._rows(wizard, monthly=True)

        for measure in ('opening_qty', 'closing_value'):
            action = self.env['l10n_ua.material.report.line'
                              ].action_open_movements(
                [('id', 'in', row.ids)], measure)
            self.assertEqual(action['type'], 'ir.actions.client')
            self.assertEqual(action['tag'], 'display_notification')
            self.assertNotIn('res_model', action)

    def test_a_row_of_the_list_opens_everything_that_moved_through_it(self):
        """A row is not a cell: it carries receipts and issues at once, so the
        button in it can only honestly offer both."""
        receipt = self._move(self.supplier, self.stock, 40,
                             datetime(2026, 3, 5, 8, 0))
        issue = self._move(self.stock, self.customer, 12,
                           datetime(2026, 3, 20, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()

        # The list shows the collapsed rows, and that is what the button is on.
        action = self._rows(wizard).action_view_movements()
        found = self.env['stock.move.line'].search(action['domain'])

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'stock.move.line')
        self.assertEqual([view_type for _id, view_type in action['views']],
                         ['list', 'form'])
        self.assertEqual(found, receipt.move_line_ids | issue.move_line_ids)

    def test_a_row_button_keeps_to_its_own_storage_place(self):
        """Rows are per place, and so are their movements: the button of one
        place has no business showing what happened in another."""
        shelf = self._shelf('Shelf F')
        into_store = self._move(self.supplier, self.stock, 30,
                                datetime(2026, 3, 3, 8, 0))
        into_shelf = self._move(self.supplier, shelf, 8,
                                datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        of_shelf = self._rows(wizard).filtered(
            lambda line: line.location_id == shelf)

        action = of_shelf.action_view_movements()
        found = self.env['stock.move.line'].search(action['domain'])

        self.assertEqual(found, into_shelf.move_line_ids)
        self.assertNotIn(into_store.move_line_ids, found)

    def test_a_row_button_keeps_to_the_period_of_the_report(self):
        """The opening balance is made of older movements, and they stay out:
        the button shows the period the report is about, not the whole life of
        the product."""
        older = self._move(self.supplier, self.stock, 9,
                           datetime(2026, 2, 10, 8, 0))
        inside = self._move(self.supplier, self.stock, 4,
                            datetime(2026, 3, 4, 8, 0))
        wizard = self._wizard()
        wizard.action_view_report()
        row = self._rows(wizard)
        self.assertEqual(row.opening_qty, 9)

        action = row.action_view_movements()
        found = self.env['stock.move.line'].search(action['domain'])

        self.assertEqual(found, inside.move_line_ids)
        self.assertNotIn(older.move_line_ids, found)

    def test_movements_cannot_be_opened_for_another_author_rows(self):
        """The method is public like the printing one, and an empty domain
        must not open somebody else's warehouse."""
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 4, 8, 0))
        self._wizard().action_view_report()

        other = self.env['res.users'].create({
            'name': 'Nosy Storekeeper',
            'login': 'nosy.storekeeper',
            'group_ids': [(4, self.env.ref('stock.group_stock_user').id)],
        })
        with self.assertRaises(UserError):
            self.env['l10n_ua.material.report.line'].with_user(
                other).action_open_movements([], 'in_qty')
