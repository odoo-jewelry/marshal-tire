from contextlib import closing, contextmanager
from unittest import TestCase

from freezegun import freeze_time
from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import Command, SUPERUSER_ID, api
from odoo.exceptions import LockError
from odoo.sql_db import db_connect
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestHistoricalConcurrency(TransactionCase):
    @contextmanager
    def _fixture(self):
        database = db_connect(self.env.cr.dbname)
        owned = {}
        try:
            with closing(database.cursor()) as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                method = env["pos.payment.method"].create({"name": "Historical concurrency account", "split_transactions": True})
                config = env["pos.config"].create({"name": "Historical concurrency POS", "cash_control": False, "payment_method_ids": [Command.set(method.ids)]})
                with freeze_time("2026-01-02 10:00:00"):
                    session = env["pos.session"].create({"config_id": config.id})
                    session.set_opening_control(0, "")
                with freeze_time("2026-01-02 11:00:00"):
                    session.close_session_from_ui()
                category = env["product.category"].create({"name": "Historical concurrency FIFO", "property_cost_method": "fifo"})
                product = env["product.product"].create({"name": "Historical concurrency stock", "is_storable": True, "available_in_pos": True, "categ_id": category.id})
                location = config.picking_type_id.default_location_src_id
                with freeze_time("2026-01-01 10:00:00"):
                    receipt = env["stock.move"].create({"product_id": product.id, "product_uom": product.uom_id.id, "product_uom_qty": 5,
                                                        "value_manual": 500, "location_id": env.ref("stock.stock_location_suppliers").id, "location_dest_id": location.id})
                    receipt._action_confirm(merge=False)
                    receipt.quantity = 5
                    receipt.picked = True
                    receipt._action_done()
                source = env["pos.order"].create({"session_id": session.id, "state": "cancel", "amount_total": 0, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
                                                  "lines": [Command.create({"product_id": product.id, "qty": 1, "price_unit": 0, "price_subtotal": 0, "price_subtotal_incl": 0})]})
                user = env.ref("base.user_admin")
                picking = env["stock.picking"].with_user(user).browse(source.with_user(user).action_prepare_historical_stock()["res_id"])
                picking.write({"historical_session_id": session.id, "historical_reason": "Concurrency proof"})
                ordinary = env["stock.move"].create({"product_id": product.id, "product_uom": product.uom_id.id, "product_uom_qty": 2,
                                                    "location_id": location.id, "location_dest_id": env.ref("stock.stock_location_customers").id})
                owned = {"product": product.id, "template": product.product_tmpl_id.id, "category": category.id,
                         "config": config.id, "session": session.id, "method": method.id, "source": source.id,
                         "picking": picking.id, "ordinary": ordinary.id, "user": user.id}
                env.flush_all()
                cr.commit()
            yield database, owned
        finally:
            if owned:
                with closing(database.cursor()) as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    picking = env["stock.picking"].with_user(owned["user"]).browse(owned["picking"])
                    picking.unlink()
                    env["pos.order"].browse(owned["source"]).unlink()
                    moves = env["stock.move"].search([("product_id", "=", owned["product"])])
                    # Only this test's committed setup is removed; operational transactions roll back.
                    moves._write({"state": "draft"})
                    moves.move_line_ids._write({"quantity": 0, "state": "draft"})
                    moves.invalidate_recordset(["state"])
                    moves.modified(["state"])
                    env.flush_all()
                    moves.unlink()
                    env["stock.quant"].search([("product_id", "=", owned["product"])]).unlink()
                    env["pos.session"].browse(owned["session"]).unlink()
                    env["pos.config"].browse(owned["config"]).unlink()
                    env["pos.payment.method"].browse(owned["method"]).unlink()
                    env["product.template"].browse(owned["template"]).unlink()
                    env["product.category"].browse(owned["category"]).unlink()
                    env.flush_all()
                    cr.commit()

    @mute_logger("odoo.sql_db")
    def test_apply_excludes_duplicate_preparation_payment_and_stock_issue(self):
        with self._fixture() as (database, owned):
            with closing(database.cursor()) as first_cr, closing(database.cursor()) as second_cr:
                first = api.Environment(first_cr, owned["user"], {})
                second = api.Environment(second_cr, owned["user"], {})
                first["stock.picking"].browse(owned["picking"]).action_apply_historical_stock()
                second_cr.execute("SET LOCAL lock_timeout = '100ms'")
                actions = [
                    lambda: second["pos.order"].browse(owned["source"]).action_prepare_historical_stock(),
                    lambda: second["stock.picking"].browse(owned["picking"]).action_apply_historical_stock(),
                    lambda: second["pos.payment"].create({"pos_order_id": owned["source"], "payment_method_id": owned["method"], "amount": 1}),
                    lambda: second["stock.move"].browse(owned["ordinary"]).write({"quantity": 2, "picked": True}),
                ]
                for action in actions:
                    with TestCase.assertRaises(self, (LockNotAvailable, LockError)), second_cr.savepoint():
                        action()
                self.assertEqual(second["product.product"].browse(owned["product"]).qty_available, 5)
                first_cr.rollback()
                second_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_stock_change_after_snapshot_invalidates_historical_apply(self):
        with self._fixture() as (database, owned):
            with closing(database.cursor()) as first_cr, closing(database.cursor()) as second_cr:
                first = api.Environment(first_cr, owned["user"], {})
                second = api.Environment(second_cr, owned["user"], {})
                first["product.product"].browse(owned["product"]).read(["cost_recompute_revision"])
                ordinary = second["stock.move"].browse(owned["ordinary"])
                ordinary.product_uom_qty = 3
                second.flush_all()
                second_cr.commit()
                with TestCase.assertRaises(self, SerializationFailure), first_cr.savepoint():
                    first["stock.picking"].browse(owned["picking"]).action_apply_historical_stock()
                first_cr.rollback()
