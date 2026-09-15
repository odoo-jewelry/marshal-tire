from contextlib import closing, contextmanager
from datetime import timedelta

from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import Command, SUPERUSER_ID, api, fields
from odoo.exceptions import LockError, UserError
from odoo.sql_db import db_connect
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from ..models.pos_cost_recompute import _CONTEXT_KEY, _INTERNAL


@tagged("post_install", "-at_install")
class TestStockValueRepairConcurrency(TransactionCase):
    @contextmanager
    def _fixture(self):
        database = db_connect(self.env.cr.dbname)
        fixture = {}
        try:
            with closing(database.cursor()) as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                category = env["product.category"].create({
                    "name": "Stock repair concurrency", "property_cost_method": "standard",
                    "property_valuation": "periodic",
                })
                product = env["product.product"].create({
                    "name": "Stock repair concurrency", "is_storable": True, "categ_id": category.id,
                    "standard_price": 0,
                })
                warehouse = env["stock.warehouse"].search([("company_id", "=", env.company.id)], limit=1)
                receipt = env["stock.move"].create({
                    "product_id": product.id, "product_uom": product.uom_id.id,
                    "product_uom_qty": 1, "value_manual": 284.01,
                    "location_id": env.ref("stock.stock_location_suppliers").id,
                    "location_dest_id": warehouse.lot_stock_id.id,
                    "picking_type_id": warehouse.in_type_id.id,
                })
                receipt._action_confirm()
                receipt.quantity = 1
                receipt.picked = True
                receipt._action_done()
                receipt.date = fields.Datetime.now() - timedelta(days=3)
                config = env["pos.config"].create({
                    "name": "Stock repair concurrency", "picking_type_id": warehouse.pos_type_id.id,
                })
                session = env["pos.session"].create({"config_id": config.id})
                order = env["pos.order"].create({
                    "session_id": session.id, "state": "paid", "amount_total": 1000,
                    "amount_tax": 0, "amount_paid": 1000, "amount_return": 0,
                    "lines": [Command.create({
                        "product_id": product.id, "qty": 1, "price_unit": 1000,
                        "price_subtotal": 1000, "price_subtotal_incl": 1000,
                        "is_total_cost_computed": True,
                    })],
                })
                picking = env["stock.picking"]._create_picking_from_pos_order_lines(
                    env.ref("stock.stock_location_customers").id, order.lines, warehouse.pos_type_id,
                )
                picking.pos_order_id = order
                issue = picking.move_ids
                issue.date = fields.Datetime.now() - timedelta(days=2)
                session.state = "closed"
                category.property_cost_method = "fifo"
                operations = env["pos.cost.recompute"].create([{
                    "selection_type": "orders", "order_ids": [Command.set(order.ids)],
                    "cost_mode": "all", "repair_stock_values": repair, "reason": "Concurrency test",
                } for repair in (True, True, False)])
                for operation in operations:
                    operation.action_preview()
                    if operation.repair_stock_values:
                        self.assertEqual(operation.stock_repair_count, 1, operation.stock_line_ids.skip_reason)
                        operation.acknowledge_stock_repair = True
                    else:
                        operation.allow_zero_cost = True
                fixture = {
                    "product": product.id, "template": product.product_tmpl_id.id, "category": category.id,
                    "receipt": receipt.id, "issue": issue.id, "order": order.id,
                    "operations": operations.ids, "session": session.id, "config": config.id,
                    "sequences": (config.order_seq_id | config.order_backend_seq_id
                                  | config.order_line_seq_id | config.device_seq_id).ids,
                }
                env.flush_all()
                cr.commit()
            yield database, fixture
        finally:
            if fixture:
                with closing(database.cursor()) as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    product = env["product.product"].browse(fixture["product"])
                    moves = env["stock.move"].search([("product_id", "=", product.id)])
                    accounts = moves.account_move_id
                    pickings = moves.picking_id
                    moves.with_context(**{_CONTEXT_KEY: _INTERNAL}).write({"cost_repair_line_id": False})
                    operations = env["pos.cost.recompute"].browse(fixture["operations"])
                    operations._internal_write({"state": "draft"})
                    operations.unlink()
                    env["product.value"].search([("move_id", "in", moves.ids)]).unlink()
                    # Remove only our owned, committed fixture. These private
                    # resets avoid replaying business reversals during cleanup.
                    moves._write({"state": "draft"})
                    moves.move_line_ids._write({"quantity": 0, "state": "draft"})
                    env.invalidate_all()
                    moves.filtered("origin_returned_move_id").unlink()
                    moves.exists().unlink()
                    pickings.unlink()
                    accounts.unlink()
                    env["res.currency.rate"].browse(fixture.get("rates", [])).exists().unlink()
                    env["stock.quant"].search([("product_id", "=", product.id)]).unlink()
                    order = env["pos.order"].browse(fixture["order"])
                    order._write({"state": "cancel"})
                    order.invalidate_recordset()
                    order.unlink()
                    env["pos.session"].browse(fixture["session"]).unlink()
                    env["pos.config"].browse(fixture["config"]).unlink()
                    env["ir.sequence"].browse(fixture["sequences"]).exists().unlink()
                    product.product_tmpl_id.unlink()
                    env["product.category"].browse(fixture["category"]).unlink()
                    env.flush_all()
                    cr.commit()

    def _return(self, env, fixture):
        issue = env["stock.move"].browse(fixture["issue"])
        return env["stock.move"].create({
            "product_id": issue.product_id.id, "product_uom": issue.product_uom.id,
            "product_uom_qty": 1, "origin_returned_move_id": issue.id,
            "location_id": issue.location_dest_id.id, "location_dest_id": issue.location_id.id,
        })

    def test_overlapping_repairs_and_normal_recompute(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as first_cr, closing(database.cursor()) as second_cr:
                first_env = api.Environment(first_cr, SUPERUSER_ID, {})
                second_env = api.Environment(second_cr, SUPERUSER_ID, {})
                first = first_env["pos.cost.recompute"].browse(fixture["operations"][0])
                first.action_apply()
                for operation_id in fixture["operations"]:
                    with self.assertRaises(LockError):
                        second_env["pos.cost.recompute"].browse(operation_id).action_apply()
                    second_cr.rollback()
                first_env.flush_all()
                first_cr.commit()
                same = second_env["pos.cost.recompute"].browse(first.id)
                same.action_apply()
                self.assertEqual(same.state, "done")
                self.assertAlmostEqual(same.stock_line_ids.actual_value, 284.01)
                for operation_id in fixture["operations"][1:]:
                    with self.assertRaisesRegex(UserError, "stale"):
                        second_env["pos.cost.recompute"].browse(operation_id).action_apply()

    @mute_logger("odoo.sql_db")
    def test_return_committed_after_apply_snapshot_is_detected(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                operation = reader["pos.cost.recompute"].browse(fixture["operations"][0])
                self.assertEqual(operation.state, "ready")
                self._return(writer, fixture)
                writer.flush_all()
                writer_cr.commit()
                with self.assertRaises(SerializationFailure):
                    operation.action_apply()
                reader_cr.rollback()
                with self.assertRaisesRegex(UserError, "stale"):
                    operation.action_apply()
                self.assertEqual(reader["stock.move"].browse(fixture["issue"]).value, 0)

    @mute_logger("odoo.sql_db")
    def test_writers_before_and_after_source_locks(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                operation = reader["pos.cost.recompute"].browse(fixture["operations"][0])
                self._return(writer, fixture)
                writer.flush_all()
                with self.assertRaises(LockError):
                    operation.action_apply()
                writer_cr.rollback()
                reader_cr.rollback()
                operation._lock_sources(operation.line_ids.pos_line_id)
                writer_cr.execute("SET LOCAL lock_timeout = '100ms'")
                with self.assertRaises(LockNotAvailable), writer_cr.savepoint():
                    self._return(writer, fixture)
                    writer.flush_all()
                    writer_cr.execute("SET CONSTRAINTS ALL IMMEDIATE")
                writer_cr.rollback()
                operation.action_apply()
                self.assertAlmostEqual(operation.stock_line_ids.actual_value, 284.01)

    @mute_logger("odoo.sql_db")
    def test_new_financial_link_and_currency_rate_after_snapshot(self):
        for kind in ("account", "rate"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    operation = reader["pos.cost.recompute"].browse(fixture["operations"][0])
                    self.assertEqual(operation.state, "ready")
                    if kind == "account":
                        journal = writer["account.journal"].search([
                            ("company_id", "=", writer.company.id), ("type", "=", "general"),
                        ], limit=1)
                        entry = writer["account.move"].create({"journal_id": journal.id})
                        writer["stock.move"].browse(fixture["issue"]).account_move_id = entry
                    else:
                        day = fields.Date.today() - timedelta(days=30)
                        domain = [("currency_id", "=", writer.company.currency_id.id),
                                  ("company_id", "=", writer.company.id)]
                        while writer["res.currency.rate"].search_count(domain + [("name", "=", day)]):
                            day -= timedelta(days=1)
                        rate = writer["res.currency.rate"].create({
                            "currency_id": writer.company.currency_id.id, "company_id": writer.company.id,
                            "name": day, "rate": 1.1,
                        })
                        fixture["rates"] = rate.ids
                    writer.flush_all()
                    writer_cr.commit()
                    with self.assertRaises(SerializationFailure):
                        operation.action_apply()
                    reader_cr.rollback()
                    with self.assertRaisesRegex(UserError, "stale"):
                        operation.action_apply()

    @mute_logger("odoo.sql_db")
    def test_known_draft_receipt_becomes_done(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as setup_cr:
                env = api.Environment(setup_cr, SUPERUSER_ID, {})
                receipt = env["stock.move"].browse(fixture["receipt"])
                draft = env["stock.move"].create({
                    "product_id": receipt.product_id.id, "product_uom": receipt.product_uom.id,
                    "product_uom_qty": 1, "location_id": receipt.location_id.id,
                    "location_dest_id": receipt.location_dest_id.id,
                    "picking_type_id": receipt.picking_type_id.id,
                })
                self.assertEqual(draft.state, "draft")
                env.flush_all()
                for operation in env["pos.cost.recompute"].browse(fixture["operations"][:2]):
                    operation.action_preview()
                    self.assertEqual(operation.stock_repair_count, 1, operation.stock_line_ids.skip_reason)
                    operation.acknowledge_stock_repair = True
                draft_id = draft.id
                setup_cr.commit()
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                operation = reader["pos.cost.recompute"].browse(fixture["operations"][0])
                self.assertEqual(operation.state, "ready")
                draft = writer["stock.move"].browse(draft_id)
                draft._action_confirm()
                draft.quantity = 1
                draft.picked = True
                draft._action_done()
                writer.flush_all()
                writer_cr.commit()
                with self.assertRaises(SerializationFailure):
                    operation.action_apply()

    @mute_logger("odoo.sql_db")
    def test_module_removal_with_snapshot_before_repair(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as repair_cr, closing(database.cursor()) as removal_cr:
                repair = api.Environment(repair_cr, SUPERUSER_ID, {})
                removal = api.Environment(removal_cr, SUPERUSER_ID, {})
                module = removal.ref("base.module_pos_cost_recompute")
                module._check_pos_stock_repair_removal()
                operation = repair["pos.cost.recompute"].browse(fixture["operations"][0])
                operation.action_apply()
                repair.flush_all()
                repair_cr.commit()
                with self.assertRaises(SerializationFailure), removal_cr.savepoint():
                    module.write({"state": "to remove"})
                    removal.flush_all()
                removal_cr.rollback()
                with self.assertRaisesRegex(UserError, "cannot be removed"):
                    module.write({"state": "to remove"})
                self.assertEqual(module.state, "installed")
