from contextlib import closing, contextmanager
from datetime import timedelta

from psycopg2.errors import LockNotAvailable, SerializationFailure

from odoo import Command, SUPERUSER_ID, api, fields
from odoo.exceptions import LockError, UserError
from odoo.sql_db import db_connect
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestPurchaseCostRecomputeConcurrency(TransactionCase):
    @contextmanager
    def _fixture(self, is_storable=True):
        """Own the committed fixture; never commit the test runner's cursor."""
        database = db_connect(self.env.cr.dbname)
        fixture = {}
        try:
            with closing(database.cursor()) as cr:
                env = api.Environment(cr, SUPERUSER_ID, {})
                category = env["product.category"].create({
                    "name": "Purchase cost concurrency", "property_cost_method": "fifo",
                    "property_valuation": "periodic",
                })
                product = env["product.product"].create({
                    "name": "Purchase cost concurrency", "is_storable": True,
                    "categ_id": category.id,
                })
                other_product = env["product.product"].create({
                    "name": "Purchase cost inserted product", "is_storable": True,
                    "categ_id": category.id,
                })
                vendor = env["res.partner"].create({"name": "Purchase cost concurrency vendor"})
                account = env["account.account"].search([
                    ("company_ids", "in", env.company.ids),
                    ("account_type", "=", "liability_current"),
                ], limit=1)
                tax = env["account.tax"].create({
                    "name": "Purchase cost concurrency 20%", "amount": 20,
                    "amount_type": "percent", "type_tax_use": "purchase",
                    "price_include_override": "tax_excluded",
                    "invoice_repartition_line_ids": [
                        Command.create({"repartition_type": "base"}),
                        Command.create({"repartition_type": "tax", "account_id": account.id}),
                    ],
                    "refund_repartition_line_ids": [
                        Command.create({"repartition_type": "base"}),
                        Command.create({"repartition_type": "tax", "account_id": account.id}),
                    ],
                })
                warehouse = env["stock.warehouse"].search([
                    ("company_id", "=", env.company.id),
                ], limit=1)
                purchases = env["purchase.order"]
                for index in range(2):
                    date = fields.Datetime.now() - timedelta(days=5 - index)
                    purchase = env["purchase.order"].create({
                        "partner_id": vendor.id, "picking_type_id": warehouse.in_type_id.id,
                        "date_order": date,
                        "order_line": [Command.create({
                            "product_id": product.id, "product_qty": 3,
                            "product_uom_id": product.uom_id.id,
                            "price_unit": 100, "date_planned": date,
                            "tax_ids": [Command.set(tax.ids)],
                        })],
                    })
                    purchase.button_confirm()
                    if purchase.locked:
                        purchase.button_unlock()
                    purchase.picking_ids.move_ids.write({"quantity": 3, "picked": True})
                    purchase.picking_ids.move_ids._action_done()
                    purchase.picking_ids.move_ids.date = date
                    purchases |= purchase
                issue = env["stock.move"].create({
                    "product_id": product.id,
                    "product_uom": product.uom_id.id, "product_uom_qty": 1,
                    "location_id": warehouse.lot_stock_id.id,
                    "location_dest_id": env.ref("stock.stock_location_customers").id,
                })
                issue._action_confirm()
                issue.write({"quantity": 1, "picked": True})
                issue._action_done()
                issue.date = fields.Datetime.now() - timedelta(days=3)
                if not is_storable:
                    # Keep the quantitative history produced by standard stock
                    # operations, as in an existing card with tracking disabled.
                    product.is_storable = False
                fixture = {
                    "product": product.id, "other_product": other_product.id,
                    "templates": (product | other_product).product_tmpl_id.ids,
                    "category": category.id, "vendor": vendor.id, "tax": tax.id,
                    "purchases": purchases.ids, "line": purchases[0].order_line.id,
                    "issue": issue.id, "warehouse": warehouse.id,
                }
                env.flush_all()
                cr.commit()
            yield database, fixture
        finally:
            if fixture:
                with closing(database.cursor()) as cr:
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    products = env["product.product"].browse([
                        fixture["product"], fixture["other_product"],
                    ])
                    moves = env["stock.move"].search([("product_id", "in", products.ids)])
                    pickings = moves.picking_id
                    accounts = (moves.account_move_id
                                | env["account.move"].browse(fixture.get("bills", [])))
                    if "closing_key" in fixture:
                        parameters = env["ir.config_parameter"].sudo()
                        if fixture["closing_original_value"] is None:
                            parameters.search([("key", "=", fixture["closing_key"])]).unlink()
                        else:
                            parameters.set_param(fixture["closing_key"], fixture["closing_original_value"])
                    env["product.value"].search([("move_id", "in", moves.ids)]).unlink()
                    moves._write({"state": "draft"})
                    moves.move_line_ids._write({"quantity": 0, "state": "draft"})
                    env.invalidate_all()
                    moves.filtered("origin_returned_move_id").unlink()
                    moves.exists().unlink()
                    pickings.unlink()
                    scraps = env["stock.scrap"].browse(fixture.get("scrap", [])).exists()
                    scraps._write({"state": "draft"})
                    scraps.invalidate_recordset()
                    scraps.unlink()
                    accounts = accounts.exists()
                    accounts._write({"state": "draft", "posted_before": False})
                    accounts.invalidate_recordset()
                    accounts.unlink()
                    purchases = env["purchase.order"].browse(fixture["purchases"])
                    purchases._write({"state": "cancel"})
                    purchases.invalidate_recordset()
                    purchases.unlink()
                    order = env["pos.order"].browse(fixture.get("pos_order", [])).exists()
                    order._write({"state": "cancel"})
                    order.invalidate_recordset()
                    order.unlink()
                    env["pos.session"].browse(fixture.get("session", [])).exists().unlink()
                    env["pos.config"].browse(fixture.get("config", [])).exists().unlink()
                    env["ir.sequence"].browse(fixture.get("sequences", [])).exists().unlink()
                    env["stock.quant"].search([("product_id", "in", products.ids)]).unlink()
                    env["product.value"].search([("product_id", "in", products.ids)]).unlink()
                    # Delete independently: the optional consolidation addon
                    # tracks template variants while their deletion cascades.
                    for template in env["product.template"].browse(fixture["templates"]):
                        template.unlink()
                    env["account.tax"].browse(fixture["tax"]).unlink()
                    env["product.category"].browse(fixture["category"]).unlink()
                    env["res.partner"].browse(fixture["vendor"]).unlink()
                    env.flush_all()
                    cr.commit()

    def _change_source(self, env, fixture, kind):
        line = env["purchase.order.line"].browse(fixture["line"])
        issue = env["stock.move"].browse(fixture["issue"])
        if kind == "purchase_price":
            line.price_unit = 110
        elif kind == "purchase_taxes":
            line.tax_ids = False
        elif kind == "purchase_insert":
            # No stock move is created: only the purchase-child hook can touch
            # the original product for this previously unknown sibling.
            line.with_context(bypass_move_update=True).copy({
                "product_id": fixture["other_product"],
            })
        elif kind == "tax":
            env["account.tax"].browse(fixture["tax"]).amount = 21
        elif kind == "tax_child":
            env["account.tax.repartition.line"].create({
                "tax_id": fixture["tax"], "document_type": "invoice",
                "repartition_type": "tax", "factor_percent": 0,
            })
        elif kind in {"issue", "return", "inventory_gain", "inventory_loss"}:
            inventory = kind.startswith("inventory_")
            inventory_location = issue.product_id.property_stock_inventory
            env["stock.move"].create({
                "product_id": issue.product_id.id,
                "product_uom": issue.product_uom.id, "product_uom_qty": 1,
                "origin_returned_move_id": issue.id if kind == "return" else False,
                "is_inventory": inventory,
                "location_id": (inventory_location if kind == "inventory_gain"
                                else issue.location_dest_id if kind == "return"
                                else issue.location_id).id,
                "location_dest_id": (inventory_location if kind == "inventory_loss"
                                     else issue.location_id if kind in ("return", "inventory_gain")
                                     else issue.location_dest_id).id,
            })
        elif kind in {"pos_line", "pos_draft"}:
            warehouse = env["stock.warehouse"].browse(fixture["warehouse"])
            config = env["pos.config"].create({
                "name": "Purchase cost concurrent POS", "picking_type_id": warehouse.pos_type_id.id,
            })
            session = env["pos.session"].create({"config_id": config.id})
            order = env["pos.order"].create({
                "session_id": session.id, "state": "draft" if kind == "pos_draft" else "paid",
                "amount_total": 100,
                "amount_tax": 0, "amount_paid": 100, "amount_return": 0,
                "lines": [Command.create({
                    "product_id": issue.product_id.id, "qty": 1, "price_unit": 100,
                    "price_subtotal": 100, "price_subtotal_incl": 100,
                })],
            })
            fixture.update({
                "pos_order": order.ids, "session": session.ids, "config": config.ids,
                "sequences": (config.order_seq_id | config.order_backend_seq_id
                              | config.order_line_seq_id | config.device_seq_id).ids,
            })
        elif kind == "pos_state":
            env["pos.order"].browse(fixture["pos_order"]).state = "paid"
        elif kind == "bill":
            bill = env["account.move"].create({
                "move_type": "in_invoice", "partner_id": line.order_id.partner_id.id,
                "invoice_line_ids": [Command.create({
                    "product_id": line.product_id.id, "purchase_line_id": line.id,
                    "quantity": 1, "price_unit": 100,
                })],
            })
            fixture["bills"] = bill.ids
        elif kind == "manual_value":
            env["product.value"].create({"move_id": issue.id, "value": issue.value + 1})
        elif kind == "quant":
            quant = env["stock.quant"].search([
                ("product_id", "=", issue.product_id.id),
                ("location_id", "=", issue.location_id.id),
            ], limit=1)
            quant.quantity += 1
        elif kind == "product_tracking":
            issue.product_id.product_tmpl_id.is_storable = False
        elif kind == "product_type":
            issue.product_id.product_tmpl_id.type = "service"
        else:
            self.fail("Unknown concurrent source kind")

    def _assert_uncorrected_costs(self, env, fixture):
        purchases = env["purchase.order"].browse(fixture["purchases"])
        self.assertEqual(purchases.order_line.mapped("price_unit"), [100, 100])
        for line in purchases.order_line:
            self.assertEqual(line.tax_ids.ids, [fixture["tax"]])
            self.assertAlmostEqual(line.move_ids.value, 300)
        self.assertAlmostEqual(env["stock.move"].browse(fixture["issue"]).value, 100)
        self.assertAlmostEqual(env["product.product"].browse(fixture["product"]).standard_price, 100)

    def _prepare_customer_financial_fixture(self, env, fixture, kind):
        self._change_source(env, fixture, "pos_draft")
        order = env["pos.order"].browse(fixture["pos_order"])
        issue = env["stock.move"].browse(fixture["issue"])
        picking = env["stock.picking"].create({
            "picking_type_id": order.config_id.picking_type_id.id,
            "location_id": issue.location_id.id,
            "location_dest_id": issue.location_dest_id.id,
            "pos_order_id": order.id,
        })
        issue.picking_id = picking
        order.write({"state": "paid", "date_order": issue.date})
        invoice = env["account.move"].create({
            "move_type": "out_invoice", "partner_id": fixture["vendor"],
            "invoice_line_ids": [Command.create({
                "product_id": fixture["product"], "quantity": 1, "price_unit": 100,
                "tax_ids": [Command.clear()],
            })],
        })
        fixture.update(invoice=invoice.id, bills=invoice.ids)
        if kind != "invoice_link":
            order.account_move = invoice
        if kind == "reversal_link":
            reversal = invoice.copy({"move_type": "out_refund"})
            fixture.update(reversal=reversal.id, bills=(invoice | reversal).ids)
            target = reversal
        else:
            target = invoice
        if kind in ("cogs_change", "cogs_unlink", "reversal_link"):
            cogs = env["account.move.line"].create({
                "move_id": target.id, "display_type": "cogs",
                "product_id": fixture["product"] if kind == "reversal_link" else fixture["other_product"],
                "account_id": target.invoice_line_ids[:1].account_id.id,
                "balance": 0,
            })
            fixture["cogs"] = cogs.id

    def _change_customer_financial_source(self, env, fixture, kind):
        invoice = env["account.move"].browse(fixture["invoice"])
        if kind == "cogs_insert":
            env["account.move.line"].create({
                "move_id": invoice.id, "display_type": "cogs",
                "product_id": fixture["product"],
                "account_id": invoice.invoice_line_ids[:1].account_id.id, "balance": 0,
            })
        elif kind == "cogs_change":
            env["account.move.line"].browse(fixture["cogs"]).product_id = fixture["product"]
        elif kind == "cogs_unlink":
            env["account.move.line"].browse(fixture["cogs"]).unlink()
        elif kind == "reversal_link":
            env["account.move"].browse(fixture["reversal"]).reversed_entry_id = invoice
        elif kind == "invoice_link":
            env["pos.order"].browse(fixture["pos_order"]).account_move = invoice
        else:
            self.fail("Unknown customer financial source kind")

    @mute_logger("odoo.sql_db")
    def test_customer_financial_sources_cannot_escape_snapshot(self):
        for kind in ("cogs_insert", "cogs_change", "cogs_unlink", "reversal_link", "invoice_link"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                with closing(database.cursor()) as setup_cr:
                    setup = api.Environment(setup_cr, SUPERUSER_ID, {})
                    self._prepare_customer_financial_fixture(setup, fixture, kind)
                    setup.flush_all()
                    setup_cr.commit()
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {"lang": "en_US"})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    self._assert_uncorrected_costs(reader, fixture)
                    self._change_customer_financial_source(writer, fixture, kind)
                    writer.flush_all()
                    writer_cr.commit()
                    purchases = reader["purchase.order"].browse(fixture["purchases"])
                    with self.assertRaises(SerializationFailure):
                        purchases._apply_purchase_cost_recompute()
                    reader_cr.rollback()
                    reader.invalidate_all()
                    self._assert_uncorrected_costs(reader, fixture)
                    if kind in ("cogs_insert", "cogs_change", "reversal_link"):
                        with self.assertRaisesRegex(UserError, "protected cost-of-goods-sold"):
                            purchases._apply_purchase_cost_recompute()
                        self._assert_uncorrected_costs(reader, fixture)
                    else:
                        purchases._apply_purchase_cost_recompute()
                        self.assertEqual(reader["pos.order"].browse(fixture["pos_order"]).lines.total_cost, 120)
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_customer_financial_writer_waits_for_correction(self):
        for kind in ("cogs_insert", "reversal_link", "invoice_link"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                with closing(database.cursor()) as setup_cr:
                    setup = api.Environment(setup_cr, SUPERUSER_ID, {})
                    self._prepare_customer_financial_fixture(setup, fixture, kind)
                    setup.flush_all()
                    setup_cr.commit()
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    purchases = reader["purchase.order"].browse(fixture["purchases"])
                    purchases._apply_purchase_cost_recompute()
                    writer_cr.execute("SET LOCAL lock_timeout = '100ms'")
                    with self.assertRaises(Exception) as caught, writer_cr.savepoint():
                        self._change_customer_financial_source(writer, fixture, kind)
                        writer.flush_all()
                    self.assertIsInstance(caught.exception, (LockNotAvailable, LockError))
                    writer_cr.rollback()
                    self.assertEqual(purchases.order_line.mapped("price_unit"), [120, 120])
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_product_eligibility_change_cannot_escape_snapshot(self):
        for kind in ("product_tracking", "product_type"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {"lang": "en_US"})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    purchases = reader["purchase.order"].browse(fixture["purchases"])
                    product = reader["product.product"].browse(fixture["product"])
                    self.assertTrue(product.is_storable)
                    self.assertEqual(product.type, "consu")
                    self._assert_uncorrected_costs(reader, fixture)

                    self._change_source(writer, fixture, kind)
                    writer.flush_all()
                    writer_cr.commit()
                    with self.assertRaises(SerializationFailure):
                        purchases._apply_purchase_cost_recompute()
                    reader_cr.rollback()
                    reader.invalidate_all()
                    self._assert_uncorrected_costs(reader, fixture)
                    self.assertFalse(product.is_storable)

                    if kind == "product_tracking":
                        # Retry sees the committed setting and uses the proven
                        # stock history without restoring inventory tracking.
                        self.assertEqual(product.type, "consu")
                        purchases._apply_purchase_cost_recompute()
                        self.assertEqual(purchases.order_line.mapped("price_unit"), [120, 120])
                        self.assertFalse(purchases.order_line.tax_ids)
                        self.assertAlmostEqual(reader["stock.move"].browse(fixture["issue"]).value, 120)
                        self.assertFalse(product.is_storable)
                    else:
                        self.assertEqual(product.type, "service")
                        with self.assertRaisesRegex(UserError, "must contain goods"):
                            purchases._apply_purchase_cost_recompute()
                        self._assert_uncorrected_costs(reader, fixture)
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_nonstock_source_insert_cannot_escape_snapshot(self):
        for kind in ("issue", "pos_line"):
            with self.subTest(kind=kind), self._fixture(is_storable=False) as (database, fixture):
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {"lang": "en_US"})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    purchases = reader["purchase.order"].browse(fixture["purchases"])
                    product = reader["product.product"].browse(fixture["product"])
                    self.assertFalse(product.is_storable)
                    self._assert_uncorrected_costs(reader, fixture)

                    self._change_source(writer, fixture, kind)
                    writer.flush_all()
                    writer_cr.commit()
                    with self.assertRaises(SerializationFailure):
                        purchases._apply_purchase_cost_recompute()
                    reader_cr.rollback()
                    reader.invalidate_all()
                    self._assert_uncorrected_costs(reader, fixture)

                    # The new draft move or paid POS line has no completed
                    # valuation evidence. Retry must read it and reject it.
                    reason = "pending stock movements" if kind == "issue" else "stock valuation source"
                    with self.assertRaisesRegex(UserError, reason):
                        purchases._apply_purchase_cost_recompute()
                    self._assert_uncorrected_costs(reader, fixture)
                    self.assertFalse(product.is_storable)
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_overlapping_conversion_is_serialized_and_retry_is_noop(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as first_cr, closing(database.cursor()) as second_cr:
                first = api.Environment(first_cr, SUPERUSER_ID, {})
                second = api.Environment(second_cr, SUPERUSER_ID, {})
                selected = first["purchase.order"].browse(fixture["purchases"])
                selected._apply_purchase_cost_recompute()
                with self.assertRaises(LockError):
                    second["purchase.order"].browse(selected[:1].ids)._apply_purchase_cost_recompute()
                second_cr.rollback()
                first.flush_all()
                first_cr.commit()
                retried = second["purchase.order"].browse(selected.ids)
                retried._apply_purchase_cost_recompute()
                self.assertEqual(retried.order_line.mapped("price_unit"), [120, 120])
                self.assertFalse(retried.order_line.tax_ids)
                self.assertAlmostEqual(second["stock.move"].browse(fixture["issue"]).value, 120)
                second_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_sources_committed_after_snapshot_cannot_be_omitted(self):
        for kind in ("purchase_price", "purchase_taxes", "purchase_insert", "tax", "tax_child",
                     "issue", "return", "inventory_gain", "inventory_loss",
                     "pos_line", "pos_state", "bill", "manual_value", "quant"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                if kind == "pos_state":
                    with closing(database.cursor()) as setup_cr:
                        setup = api.Environment(setup_cr, SUPERUSER_ID, {})
                        self._change_source(setup, fixture, "pos_draft")
                        setup.flush_all()
                        setup_cr.commit()
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    purchase = reader["purchase.order"].browse(fixture["purchases"][:1])
                    self.assertEqual(purchase.order_line.price_unit, 100)
                    self._change_source(writer, fixture, kind)
                    writer.flush_all()
                    writer_cr.commit()
                    with self.assertRaises(SerializationFailure):
                        purchase._apply_purchase_cost_recompute()
                    reader_cr.rollback()
                    reader.invalidate_all()
                    expected = 110 if kind == "purchase_price" else 100
                    self.assertEqual(reader["purchase.order.line"].browse(fixture["line"]).price_unit,
                                     expected)
                    if kind == "purchase_taxes":
                        # A retry reads tax removal from the winning request.
                        purchase._apply_purchase_cost_recompute()
                        self.assertEqual(purchase.order_line.price_unit, 100)
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_scrap_header_change_cannot_escape_snapshot(self):
        for change in ("header", "post"):
            with self.subTest(change=change), self._fixture() as (database, fixture):
                with closing(database.cursor()) as setup_cr:
                    setup = api.Environment(setup_cr, SUPERUSER_ID, {})
                    product = setup["product.product"].browse(fixture["product"])
                    scrap = setup["stock.scrap"].create({
                        "product_id": product.id,
                        "product_uom_id": product.uom_id.id,
                        "scrap_qty": 1,
                        "location_id": setup["stock.warehouse"].browse(fixture["warehouse"]).lot_stock_id.id,
                        "scrap_location_id": product.property_stock_inventory.id,
                    })
                    fixture["scrap"] = scrap.ids
                    setup.flush_all()
                    setup_cr.commit()
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    purchase = reader["purchase.order"].browse(fixture["purchases"][:1])
                    self.assertEqual(purchase.order_line.price_unit, 100)
                    target = writer["stock.scrap"].browse(fixture["scrap"])
                    if change == "post":
                        target.do_scrap()
                    else:
                        target.scrap_qty = 2
                    writer.flush_all()
                    writer_cr.commit()
                    with self.assertRaises(SerializationFailure):
                        purchase._apply_purchase_cost_recompute()
                    reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_source_writer_before_and_after_correction_locks(self):
        with self._fixture() as (database, fixture):
            with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                purchase = reader["purchase.order"].browse(fixture["purchases"][:1])
                self._change_source(writer, fixture, "purchase_taxes")
                writer.flush_all()
                with self.assertRaises(LockError):
                    purchase._apply_purchase_cost_recompute()
                reader_cr.rollback()
                writer_cr.rollback()
                reader.invalidate_all()
                writer.invalidate_all()
                purchase._apply_purchase_cost_recompute()
                writer_cr.execute("SET LOCAL lock_timeout = '100ms'")
                with self.assertRaises(LockNotAvailable), writer_cr.savepoint():
                    self._change_source(writer, fixture, "return")
                    writer.flush_all()
                writer_cr.rollback()
                self.assertEqual(purchase.order_line.price_unit, 120)
                reader_cr.rollback()

    @mute_logger("odoo.sql_db")
    def test_new_and_existing_valuation_closings_cannot_escape_snapshot(self):
        for kind in ("new_key", "post_existing"):
            with self.subTest(kind=kind), self._fixture() as (database, fixture):
                with closing(database.cursor()) as setup_cr:
                    setup = api.Environment(setup_cr, SUPERUSER_ID, {})
                    key = "%s.stock_valuation_closing_ids" % setup.company.id
                    parameters = setup["ir.config_parameter"].sudo()
                    original = parameters.search([("key", "=", key)])
                    fixture.update(closing_key=key, closing_original_value=original.value if original else None)
                    if kind == "new_key":
                        # The test database's company must have no prior closing.
                        # Never erase an existing period boundary to force a test.
                        self.assertFalse(original, "The first-closing fixture requires no existing closing key")
                    journal = setup["account.journal"].search([
                        ("company_id", "=", setup.company.id), ("type", "=", "general"),
                    ], limit=1)
                    closing_move = setup["account.move"].create({
                        "journal_id": journal.id, "date": fields.Date.today(),
                        "ref": "Purchase cost concurrency closing",
                    })
                    fixture["bills"] = closing_move.ids
                    if kind == "post_existing":
                        setup.company._save_closing_id(closing_move.id)
                    setup.flush_all()
                    setup_cr.commit()
                with closing(database.cursor()) as reader_cr, closing(database.cursor()) as writer_cr:
                    reader = api.Environment(reader_cr, SUPERUSER_ID, {})
                    writer = api.Environment(writer_cr, SUPERUSER_ID, {})
                    purchase = reader["purchase.order"].browse(fixture["purchases"][:1])
                    self.assertEqual(purchase.order_line.price_unit, 100)
                    closing_move = writer["account.move"].browse(fixture["bills"])
                    # No accounting amount is needed to characterize a posting
                    # race. This empty, owned fixture is never a real journal entry.
                    closing_move.write({"state": "posted"})
                    if kind == "new_key":
                        writer.company._save_closing_id(closing_move.id)
                    writer.flush_all()
                    writer_cr.commit()
                    with self.assertRaises(SerializationFailure):
                        purchase._apply_purchase_cost_recompute()
                    reader_cr.rollback()
                    reader.invalidate_all()
                    self.assertEqual(purchase.order_line.price_unit, 100)
                    reader_cr.rollback()
