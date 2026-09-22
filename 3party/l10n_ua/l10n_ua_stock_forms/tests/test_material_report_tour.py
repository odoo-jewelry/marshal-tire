"""The report as it is actually used: from a browser."""

from odoo import fields
from odoo.tests import HttpCase, tagged

from .material_report_common import MaterialReportCase


@tagged('post_install', '-at_install')
class TestMaterialReportTour(MaterialReportCase, HttpCase):
    """The client side of the report, which no python test can reach.

    The wiring between the screen and the server is what keeps breaking: a
    call made through a component that the click itself destroys, an action
    handed to the client without the key it reads first, a read that answers
    an inaccessible record with an error dialog. None of that shows in a
    python test — the server methods were right every time — and each was
    found by a reader rather than by us. The tour clicks the same things they
    do.
    """

    def test_the_report_can_be_driven_from_the_screen(self):
        """One movement is enough: the report needs a row to have anything to
        click on, and the tour is about the clicking rather than the figures.

        Into the store the menu opens on, and dated now, so that it falls
        inside the period the menu asks for — the current month up to today.
        """
        self._move(self.supplier, self.warehouse.lot_stock_id, 12,
                   fields.Datetime.now())

        self.start_tour(
            '/odoo/action-l10n_ua_stock_forms.action_material_report_open',
            'l10n_ua_material_report',
            login='admin',
            timeout=90,
        )
