from contextlib import closing
from unittest import TestCase

from psycopg2.errors import LockNotAvailable

from odoo import Command, SUPERUSER_ID, api
from odoo.exceptions import LockError, UserError
from odoo.sql_db import db_connect
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionConcurrency(TransactionCase):
    @mute_logger("odoo.sql_db")
    def test_apply_serializes_competing_operational_actions(self):
        """Use real connections and remove the fixture owned by this test.

        Only setup records are committed. Both operational transactions are
        rolled back; the runner transaction is never committed.
        """
        database = db_connect(self.env.cr.dbname)
        fixture = {}
        try:
            with closing(database.cursor()) as setup_cr:
                env = api.Environment(setup_cr, SUPERUSER_ID, {})
                method = env["pos.payment.method"].create({
                    "name": "Correction concurrency customer account",
                    "split_transactions": True,
                })
                config = env["pos.config"].create({
                    "name": "Correction concurrency fixture",
                    "cash_control": False,
                    "payment_method_ids": [Command.set(method.ids)],
                })
                session = env["pos.session"].create({"config_id": config.id})
                session.set_opening_control(0, "")
                customer = env["res.partner"].create({"name": "Correction concurrency customer"})
                product = env["product.product"].create({
                    "name": "Correction concurrency service",
                    "type": "service", "available_in_pos": True,
                    "list_price": 100, "taxes_id": [Command.clear()],
                })
                order = env["pos.order"].create({
                    "session_id": session.id, "partner_id": customer.id,
                    "amount_total": 100, "amount_tax": 0,
                    "amount_paid": 100, "amount_return": 0,
                    "lines": [Command.create({
                        "product_id": product.id, "qty": 1, "price_unit": 100,
                        "price_subtotal": 100, "price_subtotal_incl": 100,
                        "tax_ids": [Command.clear()],
                    })],
                    "payment_ids": [Command.create({"payment_method_id": method.id, "amount": 100})],
                })
                order.action_pos_order_paid()
                correction = env["pos.order.correction"].browse(order.action_prepare_correction()["res_id"])
                correction.line_ids.price_unit = 110
                correction.payment_ids.amount = 110
                correction.reason = "Concurrent registration correction"
                journal = env["account.journal"].search([
                    ("company_id", "=", env.company.id), ("type", "=", "bank"),
                ], limit=1)
                payment = env["account.payment"].create({
                    "amount": 10, "payment_type": "inbound", "partner_type": "customer",
                    "partner_id": customer.id, "journal_id": journal.id,
                })
                allocation = env["pos.customer.debt.allocation"].create({
                    "payment_id": payment.id, "order_id": order.id, "amount": 10,
                })
                source_entry = env["account.move"].create({
                    "journal_id": journal.id,
                    "line_ids": [
                        Command.create({
                            "name": "Concurrent POS debt source", "debit": 100,
                            "account_id": customer.property_account_receivable_id.id,
                            "partner_id": customer.id,
                            "pos_debt_payment_id": order.payment_ids.id,
                        }),
                        Command.create({
                            "name": "Concurrent POS counterpart", "credit": 100,
                            "account_id": journal.default_account_id.id,
                        }),
                    ],
                })
                source_line = source_entry.line_ids.filtered("pos_debt_payment_id")
                fixture = {
                    "correction": correction.id, "order": order.id,
                    "session": session.id, "config": config.id,
                    "template": product.product_tmpl_id.id, "customer": customer.id,
                    "method": method.id, "payment": payment.id, "allocation": allocation.id,
                    "source_entry": source_entry.id, "source_line": source_line.id,
                    "unlinked_line": (source_entry.line_ids - source_line).id,
                    "pos_payment": order.payment_ids.id,
                    "sequences": (config.order_seq_id | config.order_backend_seq_id
                                  | config.order_line_seq_id | config.device_seq_id).ids,
                }
                env.flush_all()
                setup_cr.commit()

            with closing(database.cursor()) as first_cr, closing(database.cursor()) as second_cr:
                first = api.Environment(first_cr, SUPERUSER_ID, {})
                second = api.Environment(second_cr, SUPERUSER_ID, {"lang": "en_US"})
                first["pos.order.correction"].browse(fixture["correction"]).action_apply()
                operations = {
                    "correction": lambda: second["pos.order.correction"].browse(fixture["correction"]).action_apply(),
                    "closure": lambda: second["pos.session"].browse(fixture["session"])._validate_session(),
                    "invoice": lambda: second["pos.order"].browse(fixture["order"])._generate_pos_order_invoice(),
                    "return": lambda: second["pos.order"].browse(fixture["order"])._refund(),
                    "settlement": lambda: second["pos.customer.debt.allocation"].browse(fixture["allocation"]).action_apply(),
                    "debt_source_write": lambda: second["account.move.line"].browse(fixture["source_line"]).write({"partner_id": False}),
                    "debt_source_link": lambda: second["account.move.line"].browse(fixture["unlinked_line"]).write({"pos_debt_payment_id": fixture["pos_payment"]}),
                    "debt_source_unlink": lambda: second["account.move.line"].browse(fixture["source_line"]).unlink(),
                }
                for name, operation in operations.items():
                    with self.subTest(operation=name):
                        second_cr.execute("SET LOCAL lock_timeout = '200ms'")
                        with TestCase.assertRaises(self, (UserError, LockError, LockNotAvailable)) as caught:
                            operation()
                        if isinstance(caught.exception, UserError):
                            self.assertRegex(str(caught.exception), "processed|invoiced|concurrently")
                        second_cr.rollback()
                        second.invalidate_all(flush=False)
                first_cr.rollback()
                correction = second["pos.order.correction"].browse(fixture["correction"])
                correction.action_apply()
                self.assertEqual(correction.state, "applied")
                self.assertEqual(correction.applied_order_id.amount_total, 10)
                self.assertEqual(len(correction.root_order_id.correction_order_ids), 1)
                second_cr.rollback()
        finally:
            if fixture:
                with closing(database.cursor()) as cleanup_cr:
                    env = api.Environment(cleanup_cr, SUPERUSER_ID, {})
                    env["pos.customer.debt.allocation"].browse(fixture["allocation"]).exists().unlink()
                    env["account.payment"].browse(fixture["payment"]).exists().unlink()
                    env["pos.order.correction"].browse(fixture["correction"]).exists().unlink()
                    env["account.move"].browse(fixture["source_entry"]).exists().unlink()
                    order = env["pos.order"].browse(fixture["order"]).exists()
                    # The fixture has no posted accounting or stock. Remove
                    # only its setup record without creating a business return.
                    order._write({"state": "cancel"})
                    order.invalidate_recordset()
                    order.unlink()
                    env["pos.session"].browse(fixture["session"]).exists().unlink()
                    env["pos.config"].browse(fixture["config"]).exists().unlink()
                    env["ir.sequence"].browse(fixture["sequences"]).exists().unlink()
                    env["pos.payment.method"].browse(fixture["method"]).exists().unlink()
                    env["product.template"].browse(fixture["template"]).exists().unlink()
                    env["res.partner"].browse(fixture["customer"]).exists().unlink()
                    env.flush_all()
                    cleanup_cr.commit()
