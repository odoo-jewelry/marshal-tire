"""Which archived products still belong in a report."""

from datetime import datetime

from odoo.tests import tagged

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestArchivedProducts(MaterialReportCase):
    """Archived products.

    Out of the report unless they moved during the period — the database
    keeps no archiving history, so movement is what stands for "was in use".
    See `_moved_products` in the wizard.
    """

    def test_archived_product_without_movement_stays_out(self):
        """A balance dragged in from older times does not clutter the report."""
        self._move(self.supplier, self.stock, 9, datetime(2026, 2, 10, 8, 0))
        self.product.action_archive()

        self.assertFalse(self._wizard()._get_report_lines())

    def test_archived_product_with_movement_stays_in(self):
        """The product was in use this period — the archive is no reason to hide it."""
        self._move(self.supplier, self.stock, 9, datetime(2026, 3, 4, 8, 0))
        self.product.action_archive()

        lines = self._wizard()._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['in_qty'], 9)

    def test_archiving_the_template_hides_the_variant_too(self):
        """Usually the template is archived, while a report row carries the variant."""
        self._move(self.supplier, self.stock, 4, datetime(2026, 2, 10, 8, 0))
        self.product.product_tmpl_id.action_archive()

        self.assertFalse(self.product.active)
        self.assertFalse(self._wizard()._get_report_lines())

    def test_active_product_without_movement_keeps_its_balance_row(self):
        """The filter concerns the archive alone: an active product keeps its balance."""
        self._move(self.supplier, self.stock, 9, datetime(2026, 2, 10, 8, 0))

        lines = self._wizard()._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['opening_qty'], 9)
        self.assertEqual(lines[0]['in_qty'], 0)
