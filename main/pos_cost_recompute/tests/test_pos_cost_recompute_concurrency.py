from contextlib import closing

from odoo import Command, SUPERUSER_ID, api
from odoo.exceptions import LockError, UserError
from odoo.sql_db import db_connect
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPosCostRecomputeConcurrency(TransactionCase):
    def test_independent_transactions_serialize_application(self):
        """Real connections are needed: registry test cursors share one transaction.

        Own and remove the committed fixture; never commit the test runner cursor.
        The fixture has no payments, accounting entries or stock movements.
        """
        database = db_connect(self.env.cr.dbname)
        fixture = {}
        try:
            with closing(database.cursor()) as setup_cr:
                env = api.Environment(setup_cr, SUPERUSER_ID, {})
                config = env["pos.config"].create({"name": "Cost concurrency fixture"})
                session = env["pos.session"].create({"config_id": config.id})
                product = env["product.product"].create({
                    "name": "Cost concurrency service", "type": "service", "standard_price": 20,
                })
                order = env["pos.order"].create({
                    "session_id": session.id, "state": "paid", "amount_total": 50,
                    "amount_tax": 0, "amount_paid": 50, "amount_return": 0,
                    "lines": [Command.create({
                        "product_id": product.id, "qty": 1, "price_unit": 50,
                        "price_subtotal": 50, "price_subtotal_incl": 50,
                    })],
                })
                session.state = "closed"
                operations = env["pos.cost.recompute"].create([{
                    "selection_type": "orders", "order_ids": [Command.set(order.ids)],
                    "cost_mode": "all", "reason": "Concurrent cost test",
                } for _ in range(2)])
                for operation in operations:
                    operation.action_preview()
                fixture = {
                    "operations": operations.ids, "order": order.id,
                    "session": session.id, "config": config.id,
                    "template": product.product_tmpl_id.id,
                    "sequences": (config.order_seq_id | config.order_backend_seq_id
                                  | config.order_line_seq_id | config.device_seq_id).ids,
                }
                env.flush_all()
                setup_cr.commit()

            with closing(database.cursor()) as first_cr, closing(database.cursor()) as second_cr:
                first_env = api.Environment(first_cr, SUPERUSER_ID, {})
                second_env = api.Environment(second_cr, SUPERUSER_ID, {})
                first = first_env["pos.cost.recompute"].browse(fixture["operations"][0])
                same = second_env["pos.cost.recompute"].browse(first.id)
                first.action_apply()
                with self.assertRaises(LockError):
                    same.action_apply()
                second_cr.rollback()
                first_env.flush_all()
                first_cr.commit()
                same.action_apply()
                self.assertEqual(same.state, "done")
                self.assertEqual(same.line_ids.actual_cost, 20)
                other = second_env["pos.cost.recompute"].browse(fixture["operations"][1])
                with self.assertRaisesRegex(UserError, "stale"):
                    other.action_apply()
                self.assertEqual(other.state, "ready")
                self.assertEqual(same.line_ids.pos_line_id.total_cost, 20)
                second_cr.rollback()
        finally:
            if fixture:
                with closing(database.cursor()) as cleanup_cr:
                    env = api.Environment(cleanup_cr, SUPERUSER_ID, {})
                    operations = env["pos.cost.recompute"].browse(fixture["operations"]).exists()
                    operations._internal_write({"state": "draft"})
                    operations.unlink()
                    order = env["pos.order"].browse(fixture["order"]).exists()
                    # This synthetic fixture was never paid through the POS workflow.
                    # Bypass the paid-state guard only to remove our committed fixture.
                    order._write({"state": "cancel"})
                    order.invalidate_recordset(["state"])
                    order.unlink()
                    env["pos.session"].browse(fixture["session"]).exists().unlink()
                    env["pos.config"].browse(fixture["config"]).exists().unlink()
                    env["ir.sequence"].browse(fixture["sequences"]).exists().unlink()
                    env["product.template"].browse(fixture["template"]).exists().unlink()
                    env.flush_all()
                    cleanup_cr.commit()
