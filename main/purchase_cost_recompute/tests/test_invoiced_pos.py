from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import new_test_user, tagged
from odoo.tools.translate import code_translations

from .common import PurchaseCostRecomputeCommon


@tagged("post_install", "-at_install")
class TestInvoicedPurchaseCost(PurchaseCostRecomputeCommon):
    def _invoice(self, product=None, **values):
        product = product if product is not None else self.product
        return self.env["account.move"].create({
            "move_type": "out_invoice", "partner_id": self.customer.id,
            "invoice_date": "2026-01-02",
            "invoice_line_ids": [Command.create({
                "product_id": product.id, "quantity": 1, "price_unit": 200,
                "tax_ids": [Command.clear()],
            })],
            **values,
        })

    def _add_cogs(self, invoice, product=None, amount=100):
        product = product if product is not None else self.product
        invoice.write({"line_ids": [Command.create({
            "name": "Historical cost evidence", "display_type": "cogs",
            "product_id": product.id, "balance": balance,
            "account_id": self.company_data[account].id,
        }) for balance, account in (
            (amount, "default_account_expense"), (-amount, "default_account_revenue"),
        )]})
        return invoice.line_ids.filtered(lambda line: line.display_type == "cogs")

    def _financial_snapshot(self, orders):
        invoices = orders.account_move
        documents = invoices | orders.payment_ids.account_move_id | orders.session_id.move_id
        lines = documents.line_ids
        reconciliations = lines.matched_debit_ids | lines.matched_credit_ids
        return (
            documents.read(["state", "date", "name", "amount_total", "amount_tax", "amount_residual"]),
            lines.read(["account_id", "product_id", "quantity", "price_unit", "tax_ids",
                        "debit", "credit", "balance", "amount_currency", "amount_residual",
                        "matched_debit_ids", "matched_credit_ids", "full_reconcile_id"]),
            reconciliations.read(["debit_move_id", "credit_move_id", "amount"]),
            orders.read(["state", "date_order", "amount_total", "amount_tax", "amount_paid",
                         "account_move", "payment_ids"]),
            orders.lines.read(["qty", "price_unit", "discount", "tax_ids", "price_subtotal_incl"]),
            orders.payment_ids.read(["amount", "payment_date", "payment_method_id"]),
            orders.session_id.read(["state"]),
        )

    def _cost_snapshot(self, purchase, orders):
        moves = purchase.order_line.move_ids | orders.picking_ids.move_ids
        return (
            purchase.order_line.read(["price_unit", "tax_ids"]),
            moves.read(["value", "quantity", "date", "state"]),
            orders.lines.read(["total_cost", "is_total_cost_computed"]),
            self.product.standard_price,
        )

    def test_posted_sale_refund_preserve_financials_and_repeat(self):
        purchase = self._purchase()
        sale = self._pos_order(invoiced=True)
        refund = self._pos_order(quantity=-1, date="2026-01-03 10:00:00",
                                 refund_line=sale.lines, invoiced=True)
        orders = sale | refund
        self.assertEqual(orders.account_move.mapped("state"), ["posted", "posted"])
        self.assertFalse(orders.account_move.line_ids.filtered(lambda line: line.display_type == "cogs"))
        self.assertTrue(orders.account_move.line_ids.matched_credit_ids
                        | orders.account_move.line_ids.matched_debit_ids)
        before = self._financial_snapshot(orders)
        purchase._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 120)
        self.assertEqual(refund.lines.total_cost, -120)
        self.assertEqual(sale.margin, 80)
        self.assertEqual(refund.margin, -80)
        self.assertEqual(self._financial_snapshot(orders), before)
        corrected = self._cost_snapshot(purchase, orders)
        self.assertEqual(purchase._apply_purchase_cost_recompute()["purchase_lines"], 0)
        self.assertEqual(self._cost_snapshot(purchase, orders), corrected)

    def test_draft_and_cancelled_invoice_do_not_block(self):
        for state in ("draft", "cancel"):
            with self.subTest(state=state), self.env.cr.savepoint() as savepoint:
                purchase = self._purchase()
                sale = self._pos_order()
                invoice = self._invoice()
                if state == "cancel":
                    invoice.button_cancel()
                sale.account_move = invoice
                before = self._financial_snapshot(sale)
                purchase._apply_purchase_cost_recompute()
                self.assertEqual(sale.lines.total_cost, 120)
                self.assertEqual(invoice.state, state)
                self.assertEqual(self._financial_snapshot(sale), before)
                savepoint.rollback()

    def test_partial_payment_reconciliation_is_preserved(self):
        purchase = self._purchase()
        sale = self._pos_order(invoiced=True)
        receivable = sale.account_move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        payment_line = receivable.matched_credit_ids.credit_move_id
        self.assertEqual(len(payment_line), 1)
        receivable.remove_move_reconcile()
        self.env["account.partial.reconcile"].create({
            "debit_move_id": receivable.id, "credit_move_id": payment_line.id,
            "amount": 80, "debit_amount_currency": 80, "credit_amount_currency": 80,
        })
        self.assertEqual(sale.account_move.amount_residual, 120)
        before = self._financial_snapshot(sale)
        purchase._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 120)
        self.assertEqual(self._financial_snapshot(sale), before)

    def test_nonstock_invoiced_sale_refund_use_history(self):
        purchase = self._purchase()
        sale = self._pos_order(invoiced=True)
        refund = self._pos_order(quantity=-1, date="2026-01-03 10:00:00",
                                 refund_line=sale.lines, invoiced=True)
        self._purchase(price=900, taxes=self.env["account.tax"], date="2026-01-04 10:00:00")
        self.product.write({"is_storable": False, "standard_price": 777})
        before = self._financial_snapshot(sale | refund)
        purchase._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 120)
        self.assertEqual(refund.lines.total_cost, -120)
        self.assertFalse(self.product.is_storable)
        self.assertEqual(self._financial_snapshot(sale | refund), before)

    def test_invoiced_closed_shared_source(self):
        purchase = self._purchase(quantity=5)
        self.company.point_of_sale_update_stock_quantities = "closing"
        self.company.anglo_saxon_accounting = False
        first = self._pos_order(invoiced=True)
        second = self._pos_order(quantity=3, date="2026-01-02 11:00:00")
        self._close_pos_session()
        self.assertFalse((first | second).picking_ids)
        before = self._financial_snapshot(first | second)
        result = purchase._apply_purchase_cost_recompute()
        self.assertEqual(result["pos_lines"], 2)
        self.assertEqual(first.lines.total_cost, 120)
        self.assertEqual(second.lines.total_cost, 360)
        self.assertEqual(self._financial_snapshot(first | second), before)

    def test_cogs_reversal_and_zero_entries_reject_atomically(self):
        for reversed_document, amount in ((False, 100), (True, 100), (True, 0)):
            with self.subTest(reversal=reversed_document, amount=amount), self.env.cr.savepoint() as sp:
                purchase = self._purchase()
                sale = self._pos_order()
                invoice = self._invoice()
                sale.account_move = invoice
                target = self._invoice(move_type="out_refund", reversed_entry_id=invoice.id) if reversed_document else invoice
                self._add_cogs(target, amount=amount)
                if amount == 0:
                    # Existing imported cancellation evidence still needs protection.
                    target.state = "cancel"
                before = self._cost_snapshot(purchase, sale)
                with self.assertRaisesRegex(UserError, "protected cost-of-goods-sold") as error:
                    purchase._apply_purchase_cost_recompute()
                self.assertIn(sale.display_name, str(error.exception))
                self.assertEqual(self._cost_snapshot(purchase, sale), before)
                sp.rollback()

    def test_historical_posted_cogs_survive_configuration_change(self):
        purchase = self._purchase()
        sale = self._pos_order()
        self.category.property_valuation = "real_time"
        with freeze_time("2026-01-02 11:00:00"):
            sale.with_context(generate_pdf=False).action_pos_order_invoice()
        cogs = sale.account_move.line_ids.filtered(lambda line: line.display_type == "cogs")
        self.assertTrue(cogs)
        self.category.property_valuation = "periodic"
        before = self._financial_snapshot(sale)
        with self.assertRaisesRegex(UserError, "protected cost-of-goods-sold"):
            purchase._apply_purchase_cost_recompute()
        self.assertEqual(self._financial_snapshot(sale), before)

    def test_cogs_for_other_product_do_not_block_shared_invoice(self):
        purchase = self._purchase()
        sale = self._pos_order()
        other = self.create_product("Other invoiced product", self.category, 200, 100)
        invoice = self._invoice(product=other)
        sale.account_move = invoice
        self._add_cogs(invoice, product=other)
        before = self._financial_snapshot(sale)
        purchase._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 120)
        self.assertEqual(self._financial_snapshot(sale), before)

    def test_hidden_invoice_protection_and_no_accounting_write_permission(self):
        purchase = self._purchase()
        sale = self._pos_order()
        invoice = self._invoice()
        sale.account_move = invoice
        cogs = self._add_cogs(invoice)
        user = new_test_user(
            self.env, login="invoiced-cost-manager",
            groups="purchase.group_purchase_manager,stock.group_stock_manager,"
                   "point_of_sale.group_pos_manager,product.group_product_manager",
            company_id=self.company.id,
        )
        self.env["ir.rule"].create({
            "name": "Hide invoiced cost financial document",
            "model_id": self.env["ir.model"]._get("account.move").id,
            "domain_force": f"[('id', '!=', {invoice.id})]",
        })
        with self.assertRaises(AccessError):
            invoice.with_user(user).read(["amount_total"])
        with self.assertRaisesRegex(UserError, "protected cost-of-goods-sold"):
            purchase.with_user(user)._apply_purchase_cost_recompute()
        cogs.sudo().unlink()
        purchase.with_user(user)._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 120)

    def test_invoiced_late_failure_rolls_back_and_dialog_cancel_is_inert(self):
        purchase = self._purchase()
        sale = self._pos_order(invoiced=True)
        before = self._cost_snapshot(purchase, sale), self._financial_snapshot(sale)
        action = purchase.action_open_cost_recompute()
        self.env[action["res_model"]].browse(action["res_id"]).unlink()
        self.assertEqual((self._cost_snapshot(purchase, sale), self._financial_snapshot(sale)), before)
        original = type(sale.lines)._compute_total_cost

        def fail_after_cost(lines, moves):
            original(lines, moves)
            raise UserError("Late invoiced cost failure")

        with patch.object(type(sale.lines), "_compute_total_cost", fail_after_cost):
            with self.assertRaisesRegex(UserError, "Late invoiced cost failure"):
                purchase._apply_purchase_cost_recompute()
        self.assertEqual((self._cost_snapshot(purchase, sale), self._financial_snapshot(sale)), before)
        purchase._apply_purchase_cost_recompute()
        self.assertEqual(sale.lines.total_cost, 120)

    def test_invoiced_diagnostics_have_russian_translations(self):
        with patch.dict(code_translations.python_translations, clear=True):
            translations = code_translations.get_python_translations("purchase_cost_recompute", "ru_RU")
            for source in (
                "Related customer financial documents contain protected cost-of-goods-sold entries.",
                "Related POS financial documents must belong to the order company.",
            ):
                self.assertIn(source, translations)
                self.assertNotEqual(translations[source], source)
