from contextlib import closing, contextmanager
from datetime import timedelta
from unittest import SkipTest, TestCase
from uuid import uuid4

from freezegun import freeze_time
from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import Command, SUPERUSER_ID, api, fields, models
from odoo.exceptions import LockError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "purchase_history_concurrency")
class TestPurchaseHistoryConcurrency(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not hasattr(cls.env["purchase.order"], "_apply_purchase_cost_recompute"):
            raise SkipTest("Purchase Cost Recompute is not installed")

    @contextmanager
    def _fixture(self):
        # Import only after checking the optional addon; reuse its fixture,
        # never inherit its test methods or commit the test runner's cursor.
        from odoo.addons.purchase_cost_recompute.tests.test_purchase_cost_recompute_concurrency import (
            TestPurchaseCostRecomputeConcurrency,
        )

        with TestPurchaseCostRecomputeConcurrency._fixture(self) as (database, fixture):
            owned = {}
            try:
                with closing(database.cursor()) as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    product = env["product.product"].browse(fixture["product"])
                    user = env["res.users"].create({
                        "name": "Purchase history concurrency", "login": "purchase-history-" + uuid4().hex,
                        "company_id": env.company.id, "company_ids": [Command.set(env.company.ids)],
                        "group_ids": [Command.set([env.ref(name).id for name in (
                            "purchase.group_purchase_manager",
                            "stock.group_stock_manager",
                            "product.group_product_manager",
                            "product_card_consolidation.group_product_consolidation_manager",
                            "pos_historical_stock_writeoff.group_historical_stock",
                        )])],
                    })
                    canonical = product.product_tmpl_id
                    absorbed = canonical.copy({"name": "Purchase history absorbed source"})
                    service = env["product.card.consolidation.service"].with_user(user)
                    plan = service.analyze(canonical, absorbed, mode="history")
                    self.assertFalse(plan["blockers"], plan["blockers"])
                    service.consolidate(canonical, absorbed, mode="history",
                                        expected_fingerprint=plan["fingerprint"])
                    self.assertTrue(canonical._has_full_consolidation_history(env.company))

                    method = env["pos.payment.method"].create({
                        "name": "Purchase history concurrency account", "split_transactions": True,
                    })
                    warehouse = env["stock.warehouse"].browse(fixture["warehouse"])
                    config = env["pos.config"].create({
                        "name": "Purchase history concurrency POS", "cash_control": False,
                        "picking_type_id": warehouse.pos_type_id.id,
                        "payment_method_ids": [Command.set(method.ids)],
                    })
                    stamp = fields.Datetime.now() - timedelta(days=2)
                    with freeze_time(stamp - timedelta(hours=1)):
                        target_session = env["pos.session"].create({"config_id": config.id})
                        target_session.set_opening_control(0, "")
                    with freeze_time(stamp):
                        target_session.close_session_from_ui()
                    source_session = env["pos.session"].create({"config_id": config.id})
                    source_session.set_opening_control(0, "")
                    source = env["pos.order"].create({
                        "session_id": source_session.id, "state": "cancel",
                        "amount_total": 0, "amount_tax": 0, "amount_paid": 0, "amount_return": 0,
                        "lines": [Command.create({
                            "product_id": product.id, "qty": 1, "price_unit": 0,
                            "price_subtotal": 0, "price_subtotal_incl": 0,
                        })],
                    })
                    action = source.with_user(user).action_prepare_historical_stock()
                    picking = env["stock.picking"].with_user(user).browse(action["res_id"])
                    picking.write({
                        "historical_session_id": target_session.id,
                        "historical_effective_at": stamp,
                        "historical_reason": "Purchase history concurrency proof",
                    })
                    picking.action_apply_historical_stock()
                    self.assertAlmostEqual(picking.move_ids.value, 100)
                    owned = {
                        "user": user.id, "partner": user.partner_id.id,
                        "source_template": absorbed.id,
                        "source_product": absorbed.with_context(active_test=False).product_variant_ids.id,
                        "audits": canonical._full_history_operations(env.company).ids,
                        "method": method.id, "config": config.id,
                        "source_session": source_session.id, "historical_session": target_session.id,
                        "source_order": source.id, "source_lines": source.lines.ids,
                        "historical_picking": picking.id, "historical_moves": picking.move_ids.ids,
                        "sequences": (config.order_seq_id | config.order_backend_seq_id
                                      | config.order_line_seq_id | config.device_seq_id).ids,
                        "extra_templates": [],
                    }
                    fixture.update(owned)
                    env.flush_all()
                    cr.commit()
                yield database, fixture
            finally:
                if owned:
                    with closing(database.cursor()) as cr:
                        env = api.Environment(cr, owned["user"], {}, su=True)
                        picking = env["stock.picking"].browse(owned["historical_picking"])
                        moves = picking.move_ids
                        # Remove only this fixture's committed records. The
                        # production lifecycle intentionally forbids this reset.
                        moves._write({"state": "draft"})
                        moves.move_line_ids._write({"quantity": 0, "state": "draft"})
                        picking._write({"state": "draft"})
                        env.invalidate_all()
                        picking.unlink()
                        env["pos.order"].browse(owned["source_order"]).unlink()
                        sessions = env["pos.session"].browse([
                            owned["source_session"], owned["historical_session"],
                        ])
                        sessions._write({"state": "closed"})
                        sessions.invalidate_recordset()
                        sessions.unlink()
                        env["pos.config"].browse(owned["config"]).unlink()
                        env["ir.sequence"].browse(owned["sequences"]).exists().unlink()
                        env["pos.payment.method"].browse(owned["method"]).unlink()

                        sources = env["product.template"].with_context(active_test=False).browse(
                            [owned["source_template"], *owned["extra_templates"]],
                        ).exists()
                        source_products = sources.product_variant_ids
                        env["stock.move"].search([("product_id", "in", source_products.ids)]).unlink()
                        env["stock.quant"].search([("product_id", "in", source_products.ids)]).unlink()
                        audits = env["product.consolidation.operation"].browse(owned["audits"])
                        models.Model.unlink(audits.line_ids)
                        models.Model.unlink(audits)
                        sources.with_context(product_consolidation_write=True).merged_into_id = False
                        for template in sources:
                            template.unlink()
                        env.flush_all()
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        env["res.users"].browse(owned["user"]).unlink()
                        env["res.partner"].browse(owned["partner"]).unlink()
                        env.flush_all()
                        cr.commit()

    def _change_consolidation_source(self, env, fixture, kind):
        product = env["product.product"].browse(fixture["product"])
        if kind == "membership":
            source = product.product_tmpl_id.copy({"name": "New uncovered absorbed source"})
            fixture["extra_templates"].append(source.id)
            source.with_context(product_consolidation_write=True).write({
                "merged_into_id": product.product_tmpl_id.id, "active": False,
            })
            return
        source = env["product.product"].browse(fixture["source_product"])
        location = env["stock.move"].browse(fixture["issue"]).location_id
        if kind == "move":
            env["stock.move"].create({
                "product_id": source.id, "product_uom": source.uom_id.id,
                "product_uom_qty": 1, "location_id": location.id,
                "location_dest_id": env.ref("stock.stock_location_customers").id,
            })
        elif kind == "quant":
            env["stock.quant"]._update_available_quantity(source, location, 1)
        else:
            self.fail("Unknown consolidation source change")

    def _assert_uncorrected(self, env, fixture):
        purchases = env["purchase.order"].browse(fixture["purchases"])
        self.assertEqual(purchases.order_line.mapped("price_unit"), [100, 100])
        for line in purchases.order_line:
            self.assertEqual(line.tax_ids.ids, [fixture["tax"]])
            self.assertAlmostEqual(line.move_ids.value, 300)
        self.assertAlmostEqual(env["stock.move"].browse(fixture["historical_moves"]).value, 100)
        self.assertAlmostEqual(env["stock.move"].browse(fixture["issue"]).value, 100)

    @mute_logger("odoo.sql_db")
    def test_invisible_consolidation_changes_invalidate_purchase_correction(self):
        for kind in ("membership", "move", "quant"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, fixture["user"], {"lang": "en_US"})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    purchases = reader["purchase.order"].browse(fixture["purchases"])
                    self._assert_uncorrected(reader, fixture)
                    self._change_consolidation_source(writer, fixture, kind)
                    writer.flush_all()
                    writer_cr.commit()
                    with TestCase.assertRaises(self, SerializationFailure):
                        purchases._apply_purchase_cost_recompute()
                    reader_cr.rollback()
                    reader.invalidate_all()
                    self._assert_uncorrected(reader, fixture)
                    with TestCase.assertRaises(self, UserError):
                        purchases._apply_purchase_cost_recompute()
                    self._assert_uncorrected(reader, fixture)
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_consolidation_writers_wait_for_purchase_parent_locks(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, fixture["user"], {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                purchases = reader["purchase.order"].browse(fixture["purchases"])
                purchases._lock_purchase_cost_parents()
                writer_cr.execute("SET LOCAL lock_timeout = '100ms'")
                for kind in ("membership", "move", "quant"):
                    with self.subTest(kind=kind):
                        with TestCase.assertRaises(self, (LockNotAvailable, LockError)), writer_cr.savepoint():
                            self._change_consolidation_source(writer, fixture, kind)
                            writer.flush_all()
                purchases._apply_purchase_cost_recompute()
                self.assertEqual(purchases.order_line.mapped("price_unit"), [120, 120])
                self.assertAlmostEqual(reader["stock.move"].browse(fixture["historical_moves"]).value, 120)
                reader_cr.rollback()
                writer_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_historical_session_change_after_snapshot_invalidates_correction(self):
        for key in ("source_session", "historical_session"):
            with self.subTest(session=key), self._fixture() as (database, fixture):
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, fixture["user"], {})
                    writer = api.Environment(writer_cr, fixture["user"], {})
                    purchases = reader["purchase.order"].browse(fixture["purchases"])
                    self._assert_uncorrected(reader, fixture)
                    if key == "historical_session":
                        # A config allows only one active session. Close the
                        # other owned session before changing the historical one.
                        writer["pos.session"].browse(fixture["source_session"]).state = "closed"
                    writer["pos.session"].browse(fixture[key]).state = "closing_control"
                    writer.flush_all()
                    writer_cr.commit()
                    with TestCase.assertRaises(self, SerializationFailure):
                        purchases._apply_purchase_cost_recompute()
                    reader_cr.rollback()
                    reader.invalidate_all()
                    self._assert_uncorrected(reader, fixture)
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_plan_locks_historical_documents_and_both_sessions(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, fixture["user"], {})
                writer = api.Environment(writer_cr, fixture["user"], {})
                purchases = reader["purchase.order"].browse(fixture["purchases"])
                purchases._prepare_purchase_cost_plan()
                records = (
                    writer["pos.order"].browse(fixture["source_order"]),
                    writer["pos.order.line"].browse(fixture["source_lines"]),
                    writer["pos.session"].browse(fixture["source_session"]),
                    writer["pos.session"].browse(fixture["historical_session"]),
                    writer["stock.picking"].browse(fixture["historical_picking"]),
                    writer["stock.move"].browse(fixture["historical_moves"]),
                    writer["stock.move"].browse(fixture["historical_moves"]).move_line_ids,
                )
                for recordset in records:
                    with self.subTest(model=recordset._name, ids=recordset.ids):
                        with TestCase.assertRaises(self, LockError):
                            recordset.lock_for_update()
                self._assert_uncorrected(reader, fixture)
                reader_cr.rollback()
                writer_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_completed_source_rejects_new_product_line_and_state_change(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, fixture["user"], {})
                writer = api.Environment(writer_cr, fixture["user"], {"lang": "en_US"})
                self._assert_uncorrected(reader, fixture)
                source = writer["pos.order"].browse(fixture["source_order"])
                actions = (
                    lambda: writer["pos.order.line"].create({
                        "order_id": source.id, "product_id": fixture["other_product"],
                        "qty": 1, "price_unit": 0, "price_subtotal": 0, "price_subtotal_incl": 0,
                    }),
                    lambda: source.write({"state": "draft"}),
                )
                for action in actions:
                    with TestCase.assertRaises(self, UserError), writer_cr.savepoint():
                        action()
                writer_cr.commit()
                purchases = reader["purchase.order"].browse(fixture["purchases"])
                purchases._apply_purchase_cost_recompute()
                self.assertEqual(purchases.order_line.mapped("price_unit"), [120, 120])
                self.assertAlmostEqual(reader["stock.move"].browse(fixture["historical_moves"]).value, 120)
                unchanged = reader["pos.order"].browse(fixture["source_order"])
                self.assertEqual(unchanged.state, "cancel")
                self.assertEqual(unchanged.lines.ids, fixture["source_lines"])
                reader_cr.rollback()
