from contextlib import closing, contextmanager
from datetime import timedelta

from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import SUPERUSER_ID, api, fields
from odoo.sql_db import db_connect
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.addons.stock_account.tests.common import TestStockValuationCommon


@tagged("post_install", "-at_install")
class TestStockValueRepairDiscovery(TestStockValuationCommon):
    """Characterize standard valuation before adding a protected repair path."""

    def _historical_zero_issue(self):
        product = self.product_standard
        product.standard_price = 0
        receipt = self._make_in_move(product, 1, 284.01)
        receipt.date = fields.Datetime.now() - timedelta(days=3)
        self.assertAlmostEqual(receipt.value, 284.01)
        self.assertEqual(product.standard_price, 0)
        issue = self._make_out_move(product, 1)
        issue.date = fields.Datetime.now() - timedelta(days=2)
        self.assertEqual(issue.value, 0)
        product.categ_id.property_cost_method = "fifo"
        self.assertAlmostEqual(product.standard_price, 284.01)
        self.assertEqual(issue.value, 0)
        later = self._make_in_move(product, 1, 900)
        later.date = fields.Datetime.now() - timedelta(days=1)
        self.assertAlmostEqual(product.standard_price, 900)
        return product, receipt, issue, later

    def test_manual_outgoing_valuation_uses_current_fifo(self):
        _product, receipt, issue, _later = self._historical_zero_issue()
        issue.value_manual = receipt.value
        self.assertAlmostEqual(issue.value, 900)
        history = self.env["product.value"].search([("move_id", "=", issue.id)])
        self.assertAlmostEqual(history.value, 284.01)

    def test_fixed_value_effects_and_standard_return(self):
        product, receipt, issue, later = self._historical_zero_issue()
        moves = receipt | issue | later

        def snapshot():
            self.env.flush_all()
            self.env.invalidate_all()
            return {
                "moves": moves.read([
                    "quantity", "date", "location_id", "location_dest_id", "state",
                    "product_id", "company_id", "product_uom", "remaining_qty",
                    "remaining_value", "account_move_id", "analytic_account_line_ids",
                ]),
                "receipts": (receipt | later).mapped("value"),
                "product": product.read(["standard_price", "qty_available", "total_value"]),
                "quants": self.env["stock.quant"].search([
                    ("product_id", "=", product.id),
                ]).read(["quantity", "reserved_quantity", "location_id"]),
                "account_count": self.env["account.move"].search_count([]),
                "analytic_count": self.env["account.analytic.line"].search_count([]),
                "valuation_count": self.env["product.value"].search_count([]),
            }

        before = snapshot()
        # Discovery only: production writes must go through the reviewed service.
        issue.value = receipt.value
        self.assertEqual(snapshot(), before)
        self.assertAlmostEqual(issue._get_price_unit(), 284.01)
        returned = self.env["stock.move"].create({
            "product_id": product.id,
            "product_uom": product.uom_id.id,
            "product_uom_qty": 1,
            "location_id": issue.location_dest_id.id,
            "location_dest_id": issue.location_id.id,
            "picking_type_id": self.picking_type_in.id,
            "origin_returned_move_id": issue.id,
        })
        returned._action_confirm()
        returned.quantity = 1
        returned.picked = True
        returned._action_done()
        self.assertEqual(returned.state, "done")
        self.assertAlmostEqual(returned.value, 284.01)
        self.assertAlmostEqual(issue.value, 284.01)
        self.assertFalse(returned.account_move_id)
        self.assertFalse(returned.analytic_account_line_ids)


@tagged("post_install", "-at_install")
class TestStockRepairLockDiscovery(TransactionCase):
    """Prove visibility and FK locking with independent PostgreSQL cursors.

    Draft moves are sufficient for this protocol test: an outstanding return
    excludes repair before it changes quantities or valuation. No stock,
    payments or accounting are committed by this owned fixture.
    """

    @contextmanager
    def _committed_sources(self):
        database = db_connect(self.env.cr.dbname)
        fixture = {}
        try:
            with closing(database.cursor()) as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                product = env["product.product"].create({
                    "name": "Stock repair lock discovery", "is_storable": True,
                })
                warehouse = env["stock.warehouse"].search([
                    ("company_id", "=", env.company.id),
                ], limit=1)
                move = env["stock.move"].create({
                    "product_id": product.id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": 1,
                    "location_id": warehouse.lot_stock_id.id,
                    "location_dest_id": env.ref("stock.stock_location_customers").id,
                })
                fixture = {"product": product.id, "template": product.product_tmpl_id.id,
                           "move": move.id}
                env.flush_all()
                cr.commit()
            yield database, fixture
        finally:
            if fixture:
                with closing(database.cursor()) as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    moves = env["stock.move"].search([("product_id", "=", fixture["product"])])
                    moves.filtered("origin_returned_move_id").unlink()
                    moves.exists().unlink()
                    env["product.template"].browse(fixture["template"]).unlink()
                    env.flush_all()
                    cr.commit()

    def _create_return(self, env, move_id):
        source = env["stock.move"].browse(move_id)
        return env["stock.move"].create({
            "product_id": source.product_id.id,
            "product_uom": source.product_uom.id,
            "product_uom_qty": 1,
            "location_id": source.location_dest_id.id,
            "location_dest_id": source.location_id.id,
            "origin_returned_move_id": source.id,
        })

    @mute_logger("odoo.sql_db")
    def test_source_revision_detects_invisible_return(self):
        with self._committed_sources() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                domain = [("origin_returned_move_id", "=", fixture["move"])]
                self.assertFalse(reader["stock.move"].search(domain))
                returned = self._create_return(writer, fixture["move"])
                writer.flush_all()
                writer_cr.commit()
                # The shared source version closes the characterized gap:
                # an invisible insert now changes a parent row version.
                with self.assertRaises(SerializationFailure), reader_cr.savepoint():
                    reader["product.product"].browse(fixture["product"]).lock_for_update()
                with closing(database.cursor()) as fresh_cr:
                    fresh = api.Environment(fresh_cr, SUPERUSER_ID, {})
                    self.assertEqual(fresh["stock.move"].search(domain).ids, returned.ids)

    @mute_logger("odoo.sql_db")
    def test_parent_lock_blocks_new_reference_after_lock(self):
        with self._committed_sources() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                reader["stock.move"].browse(fixture["move"]).lock_for_update()
                writer_cr.execute("SET LOCAL lock_timeout = '100ms'")
                with self.assertRaises(LockNotAvailable), writer_cr.savepoint():
                    self._create_return(writer, fixture["move"])
                    writer.flush_all()
                    # Odoo FK constraints can be deferred until commit.
                    writer_cr.execute("SET CONSTRAINTS ALL IMMEDIATE")

    @mute_logger("odoo.sql_db")
    def test_known_row_change_is_detected_after_snapshot(self):
        with self._committed_sources() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                source = reader["stock.move"].browse(fixture["move"])
                self.assertEqual(source.product_uom_qty, 1)
                writer["stock.move"].browse(fixture["move"]).product_uom_qty = 2
                writer.flush_all()
                writer_cr.commit()
                with self.assertRaises(SerializationFailure), reader_cr.savepoint():
                    source.lock_for_update()
