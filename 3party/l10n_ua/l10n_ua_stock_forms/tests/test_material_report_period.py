"""Where the period begins and ends, and how it is cut into months."""

from datetime import date, datetime

from odoo.tests import tagged

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestMaterialReportPeriod(MaterialReportCase):
    """The period: its two ends and the months between them.

    Both ends are inclusive and both are the reader\'s days rather than UTC
    ones, so a report for July in Kyiv holds what happened at half past
    midnight on the 1st and at half past eleven on the 31st.
    """

    def test_both_ends_of_the_period_are_included(self):
        """1 to 31 July must hold what happened on the 1st and on the 31st."""
        # Local 01.07 00:30 and 31.07 23:30 — stored as UTC, three hours back.
        self._move(self.supplier, self.stock, 5, datetime(2026, 6, 30, 21, 30))
        self._move(self.supplier, self.stock, 7, datetime(2026, 7, 31, 20, 30))

        wizard = self._kyiv(self._wizard(date_from='2026-07-01',
                                         date_to='2026-07-31'))
        line = wizard._get_report_lines()[0]
        self.assertEqual(line['in_qty'], 12)
        self.assertEqual(line['opening_qty'], 0)

    def test_the_day_after_the_period_stays_out(self):
        """Late in the evening UTC is already the next day in Kyiv, and that
        day belongs to August, not to the July report."""
        self._move(self.supplier, self.stock, 9, datetime(2026, 7, 31, 21, 30))

        wizard = self._kyiv(self._wizard(date_from='2026-07-01',
                                         date_to='2026-07-31'))
        self.assertFalse(wizard._get_report_lines())

    def test_the_day_before_the_period_is_an_opening_balance(self):
        """Local 30.06 23:30 is June: not a receipt of July but its opening."""
        self._move(self.supplier, self.stock, 4, datetime(2026, 6, 30, 20, 30))

        wizard = self._kyiv(self._wizard(date_from='2026-07-01',
                                         date_to='2026-07-31'))
        line = wizard._get_report_lines()[0]
        self.assertEqual(line['opening_qty'], 4)
        self.assertEqual(line['in_qty'], 0)

    def test_the_last_second_of_the_period_is_included(self):
        """The upper bound is the next midnight taken as `<`, so the final
        second of the last day cannot fall through."""
        self._move(self.supplier, self.stock, 3,
                   datetime(2026, 7, 31, 20, 59, 59, 999999))

        wizard = self._kyiv(self._wizard(date_from='2026-07-01',
                                         date_to='2026-07-31'))
        self.assertEqual(wizard._get_report_lines()[0]['in_qty'], 3)

    def test_months_are_split_on_local_midnight(self):
        """A move at 00:30 on 1 August local belongs to the August bucket,
        even though UTC still calls it July."""
        self._move(self.supplier, self.stock, 6, datetime(2026, 7, 31, 20, 30))
        self._move(self.supplier, self.stock, 8, datetime(2026, 7, 31, 21, 30))

        wizard = self._kyiv(self._wizard(date_from='2026-07-01',
                                         date_to='2026-08-31'))
        lines = wizard._get_report_lines()
        self.assertEqual([line['date_from'] for line in lines],
                         [date(2026, 7, 1), date(2026, 8, 1)])
        self.assertEqual([line['in_qty'] for line in lines], [6, 8])

    def test_period_is_cut_into_months(self):
        """Every month of the period gets its own row with its own movement."""
        self._move(self.supplier, self.stock, 10, datetime(2026, 3, 4, 8, 0))
        self._move(self.supplier, self.stock, 6, datetime(2026, 4, 7, 8, 0))
        self._move(self.stock, self.customer, 4, datetime(2026, 5, 5, 8, 0))

        lines = self._wizard(date_from='2026-03-01',
                             date_to='2026-05-31')._get_report_lines()

        self.assertEqual([line['date_from'] for line in lines],
                         [date(2026, 3, 1), date(2026, 4, 1), date(2026, 5, 1)])
        self.assertEqual([line['in_qty'] for line in lines], [10, 6, 0])
        self.assertEqual([line['out_qty'] for line in lines], [0, 0, 4])

    def test_closing_of_one_month_opens_the_next(self):
        """Months are not computed each on its own — the balance carries over."""
        self._move(self.supplier, self.stock, 10, datetime(2026, 3, 4, 8, 0))
        self._move(self.supplier, self.stock, 6, datetime(2026, 4, 7, 8, 0))

        lines = self._wizard(date_from='2026-03-01',
                             date_to='2026-04-30')._get_report_lines()

        march, april = lines
        self.assertEqual(march['opening_qty'], 0)
        self.assertEqual(march['closing_qty'], 10)
        self.assertEqual(april['opening_qty'], march['closing_qty'])
        self.assertEqual(april['closing_qty'], 16)

    def test_a_month_without_movement_still_shows_the_balance(self):
        """The product is held — the month must show it, even without movement."""
        self._move(self.supplier, self.stock, 8, datetime(2026, 3, 4, 8, 0))

        lines = self._wizard(date_from='2026-03-01',
                             date_to='2026-04-30')._get_report_lines()

        april = lines[1]
        self.assertEqual(april['in_qty'], 0)
        self.assertEqual(april['out_qty'], 0)
        self.assertEqual(april['opening_qty'], 8)
        self.assertEqual(april['closing_qty'], 8)

    def test_edge_months_are_clipped_to_the_period(self):
        """A period starting mid-month does not drag in the rest of that month."""
        self._move(self.supplier, self.stock, 5, datetime(2026, 3, 10, 8, 0))
        self._move(self.supplier, self.stock, 7, datetime(2026, 3, 20, 8, 0))

        lines = self._wizard(date_from='2026-03-15',
                             date_to='2026-04-10')._get_report_lines()

        march = lines[0]
        self.assertEqual(march['date_from'], date(2026, 3, 15))
        self.assertEqual(march['date_to'], date(2026, 3, 31))
        # The 10.03 move predates the period, so it is an opening balance, not a receipt.
        self.assertEqual(march['opening_qty'], 5)
        self.assertEqual(march['in_qty'], 7)
        self.assertEqual(lines[1]['date_to'], date(2026, 4, 10))

    def test_months_collapse_into_one_row_for_the_list_and_the_form(self):
        """The list and the form show the period as one row: movement adds up,
        the opening balance comes from the first month and the closing one from
        the last."""
        self._move(self.supplier, self.stock, 10, datetime(2026, 2, 10, 8, 0))
        self._move(self.supplier, self.stock, 6, datetime(2026, 3, 4, 8, 0))
        self._move(self.stock, self.customer, 4, datetime(2026, 4, 7, 8, 0))

        wizard = self._wizard(date_from='2026-03-01', date_to='2026-04-30')
        wizard.action_view_report()

        self.assertEqual(len(self._rows(wizard, monthly=True)), 2)
        row = self._rows(wizard)
        self.assertEqual(len(row), 1)
        self.assertEqual(row.opening_qty, 10)
        self.assertEqual(row.in_qty, 6)
        self.assertEqual(row.out_qty, 4)
        self.assertEqual(row.closing_qty, 12)
        # The collapsed row covers the whole period, not a single month.
        self.assertEqual(row.date_from, date(2026, 3, 1))
        self.assertEqual(row.date_to, date(2026, 4, 30))
