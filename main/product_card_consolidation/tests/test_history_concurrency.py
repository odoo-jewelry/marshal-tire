from contextlib import closing, contextmanager
from unittest import TestCase
from uuid import uuid4

from psycopg2.errors import SerializationFailure

from odoo import api, Command, SUPERUSER_ID
from odoo.sql_db import db_connect
from odoo.tests import tagged, TransactionCase
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "product_full_history")
class TestHistoryConsolidationConcurrency(TransactionCase):
    @contextmanager
    def _committed_cards(self):
        database = db_connect(self.env.cr.dbname)
        owned = {}
        try:
            with closing(database.cursor()) as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                group = env.ref("product_card_consolidation.group_product_consolidation_manager")
                user = env["res.users"].create({"name": "History concurrency test", "login": "history-" + uuid4().hex,
                    "group_ids": [Command.set([group.id, env.ref("stock.group_stock_manager").id])],
                    "company_id": env.company.id, "company_ids": [Command.set(env.company.ids)]})
                category = env["product.category"].create({"name": "History concurrency FIFO",
                    "property_cost_method": "fifo", "property_valuation": "periodic"})
                templates = env["product.template"].create([{"name": name, "type": "consu", "is_storable": True,
                    "company_id": env.company.id, "categ_id": category.id} for name in ("Concurrency A", "Concurrency B")])
                owned = {"user": user.id, "partner": user.partner_id.id, "category": category.id,
                         "templates": templates.ids, "products": templates.product_variant_ids.ids}
                env.flush_all()
                cr.commit()
            yield database, owned
        finally:
            if owned:
                # Only this test's committed fixture is removed. The competing
                # merge transaction is rolled back, never its audit destroyed.
                with closing(database.cursor()) as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    env["stock.move"].search([("product_id", "in", owned["products"])]).unlink()
                    env["product.template"].browse(owned["templates"]).unlink()
                    env["product.category"].browse(owned["category"]).unlink()
                    env["res.users"].browse(owned["user"]).unlink()
                    env["res.partner"].browse(owned["partner"]).unlink()
                    env.flush_all()
                    cr.commit()

    @mute_logger("odoo.sql_db")
    def test_invisible_child_insert_invalidates_confirmation(self):
        with self._committed_cards() as (database, owned):
            with closing(database.cursor()) as first_cr, closing(database.cursor()) as second_cr:
                first = api.Environment(first_cr, owned["user"], {})
                second = api.Environment(second_cr, SUPERUSER_ID, {})
                a, b = first["product.template"].browse(owned["templates"])
                service = first["product.card.consolidation.service"]
                plan = service.analyze(a, b, mode="history")
                self.assertFalse(plan["blockers"], plan["blockers"])
                source = second["product.template"].browse(b.id).product_variant_id
                second["stock.move"].create({"product_id": source.id, "product_uom": source.uom_id.id,
                    "product_uom_qty": 1, "state": "cancel", "location_id": second.ref("stock.stock_location_stock").id,
                    "location_dest_id": second.ref("stock.stock_location_customers").id})
                second.flush_all()
                second_cr.commit()
                with TestCase.assertRaises(self, SerializationFailure):
                    service.consolidate(a, b, mode="history", expected_fingerprint=plan["fingerprint"])
                first_cr.rollback()
