"""What the report counts: balances, receipts, issues and their amounts."""

from datetime import datetime

from odoo.tests import tagged

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestMaterialReportFigures(MaterialReportCase):
    """The arithmetic of one row.

    A row is "product + storage place": what it held when the period began,
    what came and went during it, and what it holds at the end.
    """

    def test_opening_receipts_issues_and_closing(self):
        self._move(self.supplier, self.stock, 100, datetime(2026, 2, 10, 8, 0))
        self._move(self.supplier, self.stock, 40, datetime(2026, 3, 5, 8, 0))
        self._move(self.stock, self.customer, 30, datetime(2026, 3, 20, 8, 0))

        lines = self._wizard()._get_report_lines()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertEqual(line['opening_qty'], 100)
        self.assertEqual(line['in_qty'], 40)
        self.assertEqual(line['out_qty'], 30)
        self.assertEqual(line['closing_qty'], 110)
        # Amounts are quantity at the product's cost price.
        self.assertEqual(line['closing_value'], 110 * 150.0)

    def test_internal_move_is_an_issue_and_a_receipt_of_the_two_places(self):
        """Rows are per place, so a transfer inside the store moves between
        two of them: out of one, into the other. Netting it out would leave
        the balance of neither place adding up."""
        shelf = self._shelf('Shelf A')
        self._move(self.supplier, self.stock, 50, datetime(2026, 3, 3, 8, 0))
        self._move(self.stock, shelf, 20, datetime(2026, 3, 6, 8, 0))

        lines = {line['location']: line
                 for line in self._wizard()._get_report_lines()}
        self.assertEqual(set(lines), {self.stock, shelf})

        self.assertEqual(lines[self.stock]['in_qty'], 50)
        self.assertEqual(lines[self.stock]['out_qty'], 20)
        self.assertEqual(lines[self.stock]['closing_qty'], 30)

        self.assertEqual(lines[shelf]['in_qty'], 20)
        self.assertEqual(lines[shelf]['out_qty'], 0)
        self.assertEqual(lines[shelf]['closing_qty'], 20)

    def test_internal_move_leaves_the_store_balance_alone(self):
        """Whatever the split, the store still holds what it held: the two
        halves of an internal transfer cancel each other in the totals."""
        shelf = self._shelf('Shelf B')
        self._move(self.supplier, self.stock, 50, datetime(2026, 3, 3, 8, 0))
        self._move(self.stock, shelf, 20, datetime(2026, 3, 6, 8, 0))

        wizard = self._wizard()
        wizard.action_view_report()
        self.assertEqual(sum(self._rows(wizard).mapped('closing_qty')), 50)
        self.assertEqual(
            self._rows(wizard)._report_totals()['closing_value'], 50 * 150.0)

    def test_rows_are_split_by_storage_place(self):
        """Two shelves of one store are two rows of the same product."""
        first = self._shelf('Shelf 1')
        second = self._shelf('Shelf 2')
        self._move(self.supplier, first, 9, datetime(2026, 3, 2, 8, 0))
        self._move(self.supplier, second, 6, datetime(2026, 3, 4, 8, 0))

        lines = self._wizard()._get_report_lines()
        self.assertEqual(len(lines), 2)
        self.assertEqual([line['location'] for line in lines], [first, second])
        self.assertEqual([line['closing_qty'] for line in lines], [9, 6])
        # The printed row names the place it counts, not the store.
        self.assertEqual(lines[0]['place'], first.complete_name)

    def test_products_without_inventory_tracking_stay_out(self):
        """Electricity, wages and overheads pass through the store in transit:
        they are issued but never received, and in the report they used to give
        a permanently negative balance."""
        electricity = self.env['product.product'].create({
            'name': 'Electricity',
            'type': 'consu',
            'is_storable': False,
            'standard_price': 4.0,
            'categ_id': self.category.id,
        })
        self._move(self.stock, self.customer, 120, datetime(2026, 3, 5, 8, 0),
                   product=electricity)
        self._move(self.supplier, self.stock, 8, datetime(2026, 3, 6, 8, 0))

        lines = self._wizard()._get_report_lines()
        self.assertEqual([line['product'] for line in lines], [self.product])

    def test_a_movement_in_another_unit_is_counted_in_the_product_unit(self):
        """A column of the report is one number, so everything in it has to be
        in one unit. The conversion is stock's own — the report reads
        `quantity_product_uom` rather than converting each line again, which is
        also what lets the database do the summing."""
        dozen = self.env.ref('uom.product_uom_dozen')
        self._move(self.supplier, self.stock, 2, datetime(2026, 3, 4, 8, 0),
                   uom=dozen)
        self._move(self.stock, self.customer, 4, datetime(2026, 3, 6, 8, 0))

        line = self._wizard()._get_report_lines()[0]
        self.assertEqual(line['in_qty'], 24)
        self.assertEqual(line['out_qty'], 4)
        self.assertEqual(line['closing_qty'], 20)

    def test_prices_come_from_the_company_of_the_report(self):
        """`standard_price` is company-dependent and the report names its own
        company. Read in whatever company the reader happens to be in, a report
        of one company would quietly be valued at another's prices."""
        other = self.env['res.company'].create({'name': 'Second Company'})
        self.product.with_company(other).standard_price = 999.0
        self._move(self.supplier, self.stock, 3, datetime(2026, 3, 4, 8, 0))

        wizard = self._wizard()
        self.assertEqual(wizard.company_id, self.company)
        line = wizard.with_company(other)._get_report_lines()[0]

        self.assertEqual(line['price'], 150.0)
        self.assertEqual(line['closing_value'], 3 * 150.0)

    def test_zero_rows_stay_out_of_the_report(self):
        """Came and went before the period: nothing held, nothing moved, so
        the row would be four zeros and the form is better off without it."""
        self._move(self.supplier, self.stock, 5, datetime(2026, 2, 10, 8, 0))
        self._move(self.stock, self.customer, 5, datetime(2026, 2, 12, 8, 0))

        self.assertFalse(self._wizard()._get_report_lines())
