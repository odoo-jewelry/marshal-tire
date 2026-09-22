from contextlib import closing, contextmanager
from unittest import TestCase
from uuid import uuid4

from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import Command, SUPERUSER_ID, api, models
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger

from odoo.addons.pos_cost_recompute.tests.test_stock_value_repair_concurrency import TestStockValueRepairConcurrency


@tagged("post_install", "-at_install", "historical_consolidation")
class TestConsolidatedRepairConcurrency(TransactionCase):
    @contextmanager
    def _fixture(self):
        with TestStockValueRepairConcurrency._fixture(self) as (database, fixture):
            source_id = audit_id = user_id = partner_id = None
            try:
                with closing(database.cursor()) as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    canonical = env["product.product"].browse(fixture["product"]).product_tmpl_id
                    source = canonical.copy({"name": "Absorbed concurrency source"})
                    user = env["res.users"].create({
                        "name": "Consolidated repair concurrency", "login": "repair-" + uuid4().hex,
                        "company_id": env.company.id, "company_ids": [Command.set(env.company.ids)],
                        "group_ids": [Command.set([env.ref(name).id for name in (
                            "product_card_consolidation.group_product_consolidation_manager",
                            "pos_historical_stock_writeoff.group_historical_stock",
                        )])],
                    })
                    service = env["product.card.consolidation.service"].with_user(user)
                    plan = service.analyze(canonical, source, mode="history")
                    self.assertFalse(plan["blockers"], plan["blockers"])
                    service.consolidate(canonical, source, mode="history", expected_fingerprint=plan["fingerprint"])
                    audit = canonical._full_history_operations(env.company)
                    operations = env["pos.cost.recompute"].browse(fixture["operations"][:2])
                    for operation in operations:
                        operation.action_preview()
                        self.assertEqual(operation.stock_repair_count, 1, operation.stock_line_ids.skip_reason)
                        operation.acknowledge_stock_repair = True
                    source_id, audit_id = source.id, audit.id
                    user_id, partner_id = user.id, user.partner_id.id
                    fixture["source_product"] = source.with_context(active_test=False).product_variant_ids.id
                    env.flush_all()
                    cr.commit()
                yield database, fixture
            finally:
                if source_id:
                    with closing(database.cursor()) as cr:
                        env = api.Environment(cr, SUPERUSER_ID, {})
                        source = env["product.template"].browse(source_id)
                        products = source.with_context(active_test=False).product_variant_ids
                        env["stock.move"].search([("product_id", "in", products.ids)]).unlink()
                        env["stock.quant"].search([("product_id", "in", products.ids)]).unlink()
                        audit = env["product.consolidation.operation"].browse(audit_id)
                        # Only remove this test's owned, committed evidence. Public
                        # unlink intentionally forbids deleting applied audits.
                        models.Model.unlink(audit.line_ids)
                        models.Model.unlink(audit)
                        source.with_context(product_consolidation_write=True).merged_into_id = False
                        source.unlink()
                        env["res.users"].browse(user_id).unlink()
                        env["res.partner"].browse(partner_id).unlink()
                        env.flush_all()
                        cr.commit()

    def _change_source(self, env, fixture, kind):
        source = env["product.product"].browse(fixture["source_product"])
        location = env["stock.move"].browse(fixture["issue"]).location_id
        if kind == "move":
            env["stock.move"].create({
                "product_id": source.id, "product_uom": source.uom_id.id,
                "product_uom_qty": 1, "location_id": location.id,
                "location_dest_id": env.ref("stock.stock_location_customers").id,
            })
        else:
            env["stock.quant"]._update_available_quantity(source, location, 1)

    @mute_logger("odoo.sql_db")
    def test_invisible_archived_source_changes_invalidate_repair(self):
        for kind in ("move", "quant"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    operation = reader["pos.cost.recompute"].browse(fixture["operations"][0])
                    self.assertEqual(operation.state, "ready")
                    self._change_source(writer, fixture, kind)
                    writer.flush_all()
                    writer_cr.commit()
                    with TestCase.assertRaises(self, SerializationFailure):
                        operation.action_apply()
                    reader_cr.rollback()
                    with TestCase.assertRaises(self, UserError):
                        operation.action_apply()
                    self.assertEqual(reader["stock.move"].browse(fixture["issue"]).value, 0)
                    self.assertEqual(reader["pos.order"].browse(fixture["order"]).lines.total_cost, 0)

    @mute_logger("odoo.sql_db")
    def test_archived_source_writers_wait_for_repair(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                operation = reader["pos.cost.recompute"].browse(fixture["operations"][0])
                operation._lock_sources(operation.line_ids.pos_line_id)
                writer_cr.execute("SET LOCAL lock_timeout = '100ms'")
                for kind in ("move", "quant"):
                    with TestCase.assertRaises(self, LockNotAvailable), writer_cr.savepoint():
                        self._change_source(writer, fixture, kind)
                        writer.flush_all()
                operation.action_apply()
                self.assertAlmostEqual(operation.stock_line_ids.actual_value, 284.01)
