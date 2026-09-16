from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionLifecycle(PosOrderCorrectionCommon):
    def _apply_price_correction(self, order, price):
        correction = self._prepare(order)
        correction.line_ids.price_unit = price
        correction.payment_ids.amount = price
        correction.reason = "Wrong price"
        correction.action_apply()
        return correction

    def test_late_invoice_uses_effective_result(self):
        order = self._create_paid_order("correction-invoice-1")
        correction = self._apply_price_correction(order, 120)
        with self.assertRaises(UserError):
            order.action_pos_order_invoice()

        self._close_session(self.session)
        action = order.with_context(generate_pdf=False).action_pos_order_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])

        self.assertEqual(invoice.amount_total, 120)
        product_lines = invoice.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )
        self.assertEqual(len(product_lines), 1)
        self.assertEqual(product_lines.product_id, self.product100)
        self.assertEqual(product_lines.quantity, 1)
        self.assertEqual(product_lines.price_unit, 120)
        self.assertEqual(invoice.pos_order_ids, order | correction.applied_order_id)
        self.assertEqual(order.action_pos_order_invoice()["res_id"], invoice.id)
        self.assertEqual(correction.applied_order_id.action_pos_order_invoice()["res_id"], invoice.id)
        self.assertEqual(order._generate_pos_order_invoice(), invoice)
        reversals = self.env["account.move"].search([
            ("reversed_pos_order_id", "in", (order | correction.applied_order_id).ids),
        ])
        self.assertEqual(len(reversals), 2)
        income_lines = (self.session.move_id | invoice | reversals).line_ids.filtered(
            lambda line: line.account_id.account_type == "income"
        )
        self.assertEqual(sum(income_lines.mapped("balance")), -120)
        with self.assertRaises(UserError):
            order.action_prepare_correction()

    def test_return_uses_effective_line_and_blocks_more_corrections(self):
        order = self._create_paid_order("correction-return-1")
        correction = self._apply_price_correction(order, 120)
        with self.assertRaises(UserError):
            order.refund()

        self._close_session(self.session)
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )
        refund = self.env["pos.order"].browse(order.refund()["res_id"])

        self.assertEqual(refund.correction_return_root_id, order)
        self.assertEqual(refund.lines.refunded_orderline_id.order_id, correction.applied_order_id)
        self.assertEqual(refund.amount_total, -120)
        with self.assertRaises(UserError):
            order.action_prepare_correction()

    def test_repeated_apply_returns_same_order(self):
        order = self._create_paid_order("correction-repeat-1")
        correction = self._apply_price_correction(order, 110)
        applied_order = correction.applied_order_id

        action = correction.action_apply()

        self.assertEqual(action["res_id"], order.id)
        self.assertEqual(correction.action_open_applied_order()["res_id"], applied_order.id)
        self.assertEqual(len(order.correction_order_ids), 1)

    def test_invoice_created_after_preparation_blocks_apply(self):
        order = self._create_paid_order("correction-invoice-stale")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 110
        correction.payment_ids.amount = 110
        correction.reason = "Wrong price"

        order.with_context(generate_pdf=False).action_pos_order_invoice()

        with self.assertRaises(UserError):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)

    def test_ordinary_return_created_after_preparation_blocks_apply(self):
        order = self._create_paid_order("correction-return-stale")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 110
        correction.payment_ids.amount = 110
        correction.reason = "Wrong price"

        order.refund()

        with self.assertRaises(UserError):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)

    def test_cancelled_ordinary_return_keeps_history_ineligible(self):
        order = self._create_paid_order("correction-cancelled-return")
        refund = order._refund()
        refund.action_pos_order_cancel()

        self.assertEqual(refund.state, "cancel")
        with self.assertRaisesRegex(UserError, "ordinary return"):
            order.action_prepare_correction()

    def test_closed_sale_can_be_prepared_without_open_session(self):
        order = self._create_paid_order("correction-no-session")
        self._close_session(self.session)

        correction = self._prepare(order)
        self.assertFalse(correction.target_session_id)
        correction.reason = "Wrong price"
        correction.line_ids.price_unit = 120
        correction.payment_ids.amount = 120
        with self.assertRaises(UserError):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)

    def test_direct_invoice_entry_waits_for_correction_closure(self):
        order = self._create_paid_order("correction-direct-invoice")
        correction = self._apply_price_correction(order, 120)
        for invoice_orders in (order, correction.applied_order_id, order | correction.applied_order_id):
            with self.assertRaises(UserError):
                invoice_orders._generate_pos_order_invoice()
        self.assertFalse(order.account_move)

    def test_other_pos_target_session_is_rejected(self):
        order = self._create_paid_order("correction-other-pos")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 120
        correction.payment_ids.amount = 120
        correction.reason = "Wrong price"
        other_config = self.config.copy({"name": "Different correction POS"})
        other_session = self.env["pos.session"].create({"config_id": other_config.id})
        other_session.set_opening_control(0, None)
        self.assertEqual(other_session.company_id, order.company_id)
        self.assertEqual(other_session.currency_id, order.currency_id)
        correction.target_session_id = other_session

        with self.assertRaisesRegex(UserError, "original point of sale"):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)
        self.assertFalse(other_session.order_ids)

    def test_other_company_target_session_is_rejected(self):
        order = self._create_paid_order("correction-other-company")
        correction = self._prepare(order)
        other_data = self.setup_other_company()
        other_company = other_data["company"]
        self.env.user.company_ids = [Command.link(other_company.id)]
        other_config = self.env["pos.config"].with_company(other_company).create({
            "name": "Other company correction POS",
            "invoice_journal_id": other_data["default_journal_sale"].id,
        })
        other_session = self.env["pos.session"].with_company(other_company).create({
            "config_id": other_config.id,
        })
        self.assertNotEqual(other_session.company_id, order.company_id)

        with self.assertRaises(UserError):
            correction.target_session_id = other_session
        self.assertFalse(correction.applied_order_id)
        self.assertFalse(other_session.order_ids)

    def test_currency_change_after_preparation_is_rejected(self):
        order = self._create_paid_order("correction-currency-changed")
        self._close_session(self.session)
        correction = self._prepare(order)
        original_currency = order.currency_id
        foreign_config = self.other_currency_config
        foreign_methods = foreign_config.payment_method_ids
        foreign_config.payment_method_ids = [Command.clear()]
        self.config.write({
            "journal_id": foreign_config.journal_id.id,
            "invoice_journal_id": foreign_config.invoice_journal_id.id,
            "use_pricelist": True,
            "available_pricelist_ids": [Command.set(foreign_config.available_pricelist_ids.ids)],
            "pricelist_id": foreign_config.pricelist_id.id,
            "payment_method_ids": [Command.set(foreign_methods.ids)],
        })
        self.session = self.open_new_session()
        self.assertNotEqual(self.session.currency_id, original_currency)
        self.assertEqual(self.session.config_id, order.config_id)
        correction.target_session_id = self.session
        correction.payment_ids.write({"payment_method_id": self.cash_pm2.id, "amount": 120})
        correction.line_ids.price_unit = 120
        correction.reason = "Wrong price"

        with self.assertRaisesRegex(UserError, "source sale changed after preparation"):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)
        self.assertFalse(self.session.order_ids)

    def test_direct_and_pos_returns_reject_stale_or_excessive_sources(self):
        order = self._create_paid_order("correction-stale-return-source")
        correction = self._apply_price_correction(order, 120)
        self._close_session(self.session)
        self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
        current = order._get_effective_correction_lines()
        self.assertEqual(current.order_id, correction.applied_order_id)

        for source, quantity, message in (
            (order.lines, -1, "replaced by a correction"),
            (current, -2, "exceeds the current unreturned quantity"),
        ):
            for entrypoint in ("create", "sync_from_ui"):
                with self.subTest(source=source.id, entrypoint=entrypoint):
                    uuid = "correction-invalid-return-%s-%s" % (source.id, entrypoint)
                    data = self.create_ui_order_data(
                        [{"product": source.product_id, "quantity": quantity,
                          "price_unit": source.price_unit,
                          "price_subtotal": source.price_unit * quantity,
                          "price_subtotal_incl": source.price_unit * quantity,
                          "refunded_orderline_id": source.id}],
                        customer=self.customer,
                        payments=[(self.cash_pm1, source.price_unit * quantity)], uuid=uuid,
                    )
                    # Mirror the rollback of a rejected RPC request. The regex
                    # assertion itself does not create Odoo's usual savepoint.
                    with self.assertRaisesRegex(UserError, message), self.env.cr.savepoint():
                        if entrypoint == "sync_from_ui":
                            self.env["pos.order"].sync_from_ui([data])
                        else:
                            data["lines"][0][2].pop("id")
                            self.env["pos.order"].create(data)
                    self.assertFalse(self.env["pos.order"].search([("uuid", "=", uuid)]))

    def test_two_correction_sessions_invoice_only_current_products(self):
        order = self._create_paid_order("correction-invoice-history")
        self._close_session(self.session)
        sessions = self.session
        for price in (120, 80):
            self.session = self._start_pos_session(
                self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
            )
            self._apply_price_correction(order, price)
            self._close_session(self.session)
            sessions |= self.session

        action = order.with_context(generate_pdf=False).action_pos_order_invoice()
        invoice = self.env["account.move"].browse(action["res_id"])

        self.assertEqual(invoice.amount_total, 80)
        self.assertEqual(invoice.amount_residual, 0)
        self.assertEqual(len(invoice.invoice_line_ids.filtered(lambda line: line.display_type == "product")), 1)
        reversals = self.env["account.move"].search([
            ("reversed_pos_order_id", "in", order._get_correction_chain().ids),
        ])
        income_lines = (sessions.move_id | reversals | invoice).line_ids.filtered(
            lambda line: line.account_id.account_type == "income"
        )
        self.assertEqual(sum(income_lines.mapped("balance")), -80)

    def test_pos_data_and_return_preserve_mixed_effective_sources(self):
        self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
        unchanged = self.create_product("Unchanged correction product", self.categ_basic, 30, 10)
        self.adjust_inventory(unchanged, [10])
        order = self._create_orders([{
            "pos_order_lines_ui_args": [(self.product100, 1), (unchanged, 1)],
            "payments": [(self.cash_pm1, 130)], "customer": self.customer,
            "is_invoiced": False, "uuid": "correction-ticket-mixed",
        }])["correction-ticket-mixed"]
        original_ids = order.lines.ids
        first = self._prepare(order)
        replaced = first.line_ids.filtered(lambda line: line.product_id == self.product100)
        replaced.write({"product_id": self.product80.id, "price_unit": 80})
        first.payment_ids.amount = 110
        first.reason = "Wrong product"
        first.action_apply()
        second = self._prepare(order)
        second.line_ids.filtered(lambda line: line.product_id == self.product80).price_unit = 90
        second.payment_ids.amount = 120
        second.reason = "Wrong price"
        second.action_apply()
        self._close_session(self.session)

        payload = order.read_pos_data([], order.config_id)
        root_data = next(values for values in payload["pos.order"] if values["id"] == order.id)
        current = order._get_effective_correction_lines()
        self.assertTrue(root_data["correction_has_applied"])
        self.assertEqual(root_data["lines"], original_ids)
        self.assertEqual(set(root_data["correction_current_line_ids"]), set(current.ids))
        self.assertEqual(root_data["correction_current_total"], 120)
        loaded_lines = {values["id"]: values for values in payload["pos.order.line"]}
        for line in current:
            self.assertEqual(loaded_lines[line.id]["order_id"], line.order_id.id)
        self.assertEqual(len(current.order_id), 2)
        search_result = self.env["pos.order"].search_paid_order_ids(order.config_id.id, [], 100, 0)
        self.assertNotIn(first.applied_order_id.id, [item[0] for item in search_result["ordersInfo"]])
        self.assertNotIn(second.applied_order_id.id, [item[0] for item in search_result["ordersInfo"]])

        self.session = self._start_pos_session(self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0)
        refund = order._refund()
        self.assertEqual(len(refund.lines), 2)
        self.assertEqual(refund.lines.refunded_orderline_id, current)
        self.assertEqual(refund.correction_return_root_id, order)
        self.assertEqual(refund.amount_total, -120)
        request_lines = [Command.create({"refunded_orderline_id": line.id}) for line in current]
        self.assertEqual(self.env["pos.order"]._get_refunded_orders({"lines": request_lines}), order)
        refund.add_payment({"pos_order_id": refund.id, "payment_method_id": self.cash_pm1.id, "amount": -120})
        refund.action_pos_order_paid()
        refund._create_order_picking()
        self.assertEqual(refund.state, "paid")
