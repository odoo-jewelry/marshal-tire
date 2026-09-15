from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import new_test_user, tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionDebt(PosOrderCorrectionCommon):
    def _open_correction_session(self):
        self.session = self._start_pos_session(
            self.cash_pm1 | self.bank_pm1 | self.pay_later_pm, 0
        )

    def test_debt_to_cash_reconciles_inside_root_chain(self):
        order = self._create_paid_order("correction-debt-1", self.pay_later_pm)
        self._close_session(self.session)
        self._open_correction_session()

        correction = self._prepare(order)
        correction.payment_ids.payment_method_id = self.cash_pm1
        correction.reason = "Payment was cash"
        correction.action_apply()
        self.assertTrue(order.correction_pending)
        self._close_session(self.session)

        credit_lines = correction.applied_order_id.payment_ids.filtered(
            lambda payment: payment.payment_method_id == self.pay_later_pm
        ).debt_move_line_ids
        source_lines = order._get_effective_debt_source_lines()
        self.assertTrue(credit_lines)
        self.assertTrue(source_lines)
        self.assertEqual(credit_lines.account_id, source_lines.account_id)
        self.assertTrue(credit_lines.matched_debit_ids | credit_lines.matched_credit_ids)
        self.assertFalse(order.correction_pending)
        self.assertEqual(order.debt_state, "settled")
        self.assertEqual(order.debt_residual_amount, 0)
        self.assertTrue(correction.internal_partial_reconcile_ids)
        next_correction = self._prepare_after_open(order)
        self.assertEqual(next_correction.base_revision, correction.revision)

    def test_cash_to_debt_creates_one_root_debt(self):
        order = self._create_paid_order("correction-debt-2", self.cash_pm1)
        self._close_session(self.session)
        self._open_correction_session()

        correction = self._prepare(order)
        correction.payment_ids.payment_method_id = self.pay_later_pm
        correction.reason = "Payment was customer account"
        correction.action_apply()
        self._close_session(self.session)

        self.assertEqual(order.debt_state, "outstanding")
        self.assertEqual(order.debt_original_amount, 0)
        self.assertEqual(order.debt_residual_amount, 100)
        self.assertEqual(order.debt_adjustment_amount, -100)
        self.assertIn(order, self.env["pos.order"]._get_debt_candidate_orders())
        self.assertIn(order, self.env["pos.order"].search([("debt_state", "=", "outstanding")]))
        self.assertNotIn(
            correction.applied_order_id,
            self.env["pos.order"]._get_debt_candidate_orders(),
        )

    def _prepare_after_open(self, order):
        self._open_correction_session()
        return self._prepare(order)

    def test_debt_increase_has_one_target_and_keeps_other_sale(self):
        order = self._create_paid_order("correction-debt-increase", self.pay_later_pm)
        other = self._create_paid_order("correction-debt-other", self.pay_later_pm)
        self._close_session(self.session)
        correction = self._prepare_after_open(order)
        correction.line_ids.price_unit = 120
        correction.payment_ids.amount = 120
        correction.reason = "Wrong price"
        correction.action_apply()

        self.assertEqual(order.debt_residual_amount, 100)
        with self.assertRaisesRegex(UserError, "Close all correction sessions"):
            order.action_register_debt_payment()
        self._close_session(self.session)

        self.assertEqual(order.debt_residual_amount, 120)
        self.assertEqual(order.debt_original_amount, 100)
        self.assertEqual(order.debt_adjustment_amount, -20)
        self.assertEqual(other.debt_residual_amount, 100)
        self.assertNotIn(correction.applied_order_id, self.env["pos.order"]._get_debt_candidate_orders())

    def test_internal_debt_credit_allows_a_second_correction(self):
        order = self._create_paid_order("correction-debt-roundtrip", self.pay_later_pm)
        self._close_session(self.session)
        for method, expected_debt in ((self.cash_pm1, 0), (self.pay_later_pm, 100)):
            correction = self._prepare_after_open(order)
            correction.payment_ids.payment_method_id = method
            correction.reason = "Correct payment registration"
            correction.action_apply()
            self._close_session(self.session)
            self.assertEqual(order.debt_residual_amount, expected_debt)
            self.assertFalse(order._get_external_debt_partials())

    def test_settlement_consumes_only_corrected_root_sources(self):
        self.env.user.group_ids = [Command.link(self.env.ref(
            "pos_customer_debt.group_pos_customer_debt_settler"
        ).id)]
        order = self._create_paid_order("correction-settlement-root", self.pay_later_pm)
        other_sale = self._create_paid_order("correction-settlement-other-sale", self.pay_later_pm)
        other_customer = self.env["res.partner"].create({"name": "Other debt customer"})
        other_customer_sale = self._create_orders([{
            "pos_order_lines_ui_args": [(self.product100, 1)],
            "payments": [(self.pay_later_pm, 100)], "customer": other_customer,
            "uuid": "correction-settlement-other-customer",
        }])["correction-settlement-other-customer"]
        self._close_session(self.session)
        correction = self._prepare_after_open(order)
        correction.line_ids.price_unit = 120
        correction.payment_ids.amount = 120
        correction.reason = "Wrong price"
        correction.action_apply()
        self._close_session(self.session)
        sources = order._get_effective_debt_source_lines()
        self.assertEqual(len(sources), 2)
        self.assertEqual(sum(sources.mapped("amount_residual_currency")), 120)

        journal = self.company_data["default_journal_bank"]
        payment = self.env["account.payment"].create({
            "amount": 120, "payment_type": "inbound", "partner_type": "customer",
            "partner_id": self.customer.id, "journal_id": journal.id,
            "currency_id": self.company.currency_id.id,
            "payment_method_line_id": journal.inbound_payment_method_line_ids[:1].id,
            "destination_account_id": self.customer.property_account_receivable_id.id,
        })
        allocation = self.env["pos.customer.debt.allocation"].create({
            "payment_id": payment.id, "order_id": order.id, "amount": 120,
        })
        payment.action_post()

        self.assertEqual(allocation.state, "applied")
        self.assertEqual(allocation.debt_move_line_ids, sources)
        self.assertEqual(allocation.effective_amount, 120)
        self.assertEqual(order.debt_original_amount, 100)
        self.assertEqual(order.debt_payment_amount, 120)
        self.assertEqual(order.debt_adjustment_amount, -20)
        self.assertEqual(order.debt_residual_amount, 0)
        self.assertEqual(other_sale.debt_residual_amount, 100)
        self.assertEqual(other_customer_sale.debt_residual_amount, 100)
        self.assertFalse(other_sale._get_external_debt_partials())
        self.assertFalse(other_customer_sale._get_external_debt_partials())
        with self.assertRaisesRegex(UserError, "subsequent debt settlement"):
            order.action_prepare_correction()

    def test_debt_reduction_credit_does_not_consume_new_invoice(self):
        order = self._create_paid_order("correction-debt-invoice", self.pay_later_pm)
        other = self._create_paid_order("correction-debt-invoice-other", self.pay_later_pm)
        self._close_session(self.session)
        correction = self._prepare_after_open(order)
        correction.line_ids.price_unit = 80
        correction.payment_ids.amount = 80
        correction.reason = "Wrong price"
        correction.action_apply()
        self._close_session(self.session)

        self.assertEqual(order.debt_residual_amount, 80)
        self.assertTrue(correction.internal_partial_reconcile_ids)
        order.with_context(generate_pdf=False).action_pos_order_invoice()

        self.assertEqual(order.account_move.amount_total, 80)
        self.assertEqual(order.account_move.amount_residual, 80)
        self.assertEqual(order.debt_residual_amount, 80)
        self.assertEqual(other.debt_residual_amount, 100)
        self.assertTrue(all(order._get_correction_chain().payment_ids.debt_move_line_ids.mapped("reconciled")))

    def test_increased_debt_invoice_transfers_each_session_source(self):
        order = self._create_paid_order("correction-debt-invoice-increase", self.pay_later_pm)
        self._close_session(self.session)
        correction = self._prepare_after_open(order)
        correction.line_ids.price_unit = 120
        correction.payment_ids.amount = 120
        correction.reason = "Wrong price"
        correction.action_apply()
        self._close_session(self.session)

        order.with_context(generate_pdf=False).action_pos_order_invoice()

        self.assertEqual(order.account_move.amount_residual, 120)
        self.assertEqual(order.debt_residual_amount, 120)
        self.assertTrue(all(order._get_correction_chain().payment_ids.debt_move_line_ids.mapped("reconciled")))

    def test_correction_session_can_be_closed_by_a_cashier(self):
        order = self._create_paid_order("correction-debt-cashier", self.pay_later_pm)
        self._close_session(self.session)
        correction = self._prepare_after_open(order)
        correction.payment_ids.payment_method_id = self.cash_pm1
        correction.reason = "Payment was cash"
        correction.action_apply()
        cashier = new_test_user(
            self.env, login="pos_correction_closing_cashier",
            groups="base.group_user,point_of_sale.group_pos_user",
            company_id=self.company.id,
        )

        self._close_session(self.session.with_user(cashier))

        self.assertEqual(self.session.state, "closed")
        self.assertEqual(order.debt_residual_amount, 0)

    def test_cancelled_settlement_still_blocks_correction(self):
        self.env.user.group_ids = [Command.link(self.env.ref(
            "pos_customer_debt.group_pos_customer_debt_settler"
        ).id)]
        order = self._create_paid_order("correction-debt-cancelled-settlement", self.pay_later_pm)
        self._close_session(self.session)
        journal = self.company_data["default_journal_bank"]
        payment = self.env["account.payment"].create({
            "amount": 20,
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.customer.id,
            "journal_id": journal.id,
            "currency_id": self.company.currency_id.id,
            "payment_method_line_id": journal.inbound_payment_method_line_ids[:1].id,
            "destination_account_id": self.customer.property_account_receivable_id.id,
        })
        allocation = self.env["pos.customer.debt.allocation"].create({
            "payment_id": payment.id, "order_id": order.id, "amount": 20,
        })
        payment.action_post()
        payment.action_cancel()

        self.assertEqual(payment.state, "canceled")
        self.assertFalse(allocation.is_effective)
        self.assertNotEqual(allocation.state, "draft")
        self.assertEqual(order.debt_residual_amount, 100)
        with self.assertRaisesRegex(UserError, "subsequent debt settlement"):
            order.action_prepare_correction()

    def test_missing_accounting_source_blocks_preparation(self):
        order = self._create_paid_order("correction-debt-missing-source", self.pay_later_pm)
        self._close_session(self.session)
        order.payment_ids.debt_move_line_ids.pos_debt_payment_id = False

        with self.assertRaisesRegex(UserError, "unambiguous posted accounting source"):
            order.action_prepare_correction()
        self.assertFalse(order.correction_ids)

    def test_contradictory_accounting_source_blocks_preparation(self):
        order = self._create_paid_order("correction-debt-contradictory-source", self.pay_later_pm)
        self._close_session(self.session)
        other_customer = self.env["res.partner"].create({"name": "Different accounting customer"})
        order.payment_ids.debt_move_line_ids.partner_id = other_customer

        with self.assertRaisesRegex(UserError, "unambiguous posted accounting source"):
            order.action_prepare_correction()
        self.assertFalse(order.correction_ids)

    def test_accounting_source_lost_after_preparation_blocks_application(self):
        order = self._create_paid_order("correction-debt-source-lost-after-editing", self.pay_later_pm)
        self._close_session(self.session)
        correction = self._prepare_after_open(order)
        correction.payment_ids.payment_method_id = self.cash_pm1
        correction.reason = "Payment was cash"
        order.payment_ids.debt_move_line_ids.pos_debt_payment_id = False

        with self.assertRaisesRegex(UserError, "unambiguous posted accounting source"):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)
        self.assertEqual(correction.state, "draft")
