from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .common import PosCustomerDebtCommon


@tagged("post_install", "-at_install")
class TestPosCustomerDebtAllocation(PosCustomerDebtCommon):
    def setUp(self):
        super().setUp()
        _session, orders = self._close_orders(
            [
                self._pay_later_order_values("debt-allocation-1"),
                self._pay_later_order_values("debt-allocation-2"),
            ]
        )
        self.order1 = orders["debt-allocation-1"]
        self.order2 = orders["debt-allocation-2"]

    def test_exact_multi_order_distribution_and_idempotency(self):
        payment = self._create_incoming_payment(100)
        allocations = self.env["pos.customer.debt.allocation"].create(
            [
                {"payment_id": payment.id, "order_id": self.order1.id, "amount": 20},
                {"payment_id": payment.id, "order_id": self.order2.id, "amount": 50},
            ]
        )
        payment.action_post()

        self.assertEqual(self.order1.debt_residual_amount, 80)
        self.assertEqual(self.order2.debt_residual_amount, 50)
        self.assertEqual(payment.pos_debt_available_amount, 30)
        self.assertEqual(sum(allocations.mapped("effective_amount")), 70)
        partial_ids = allocations.partial_reconcile_ids.ids

        allocations.action_apply()
        self.assertEqual(allocations.partial_reconcile_ids.ids, partial_ids)

    def test_existing_payment_partial_allocation(self):
        payment = self._create_incoming_payment(60)
        payment.action_post()
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 25}
        )
        allocation.action_apply()

        self.assertEqual(self.order1.debt_residual_amount, 75)
        self.assertEqual(payment.pos_debt_available_amount, 35)

    def test_full_settlement_preserves_pos_order_state_and_payments(self):
        order_state = self.order1.state
        pos_payment_ids = self.order1.payment_ids.ids
        payment = self._create_incoming_payment(100)
        self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 100}
        )

        payment.action_post()

        self.assertEqual(self.order1.debt_state, "settled")
        self.assertEqual(self.order1.state, order_state)
        self.assertEqual(self.order1.payment_ids.ids, pos_payment_ids)
        self.assertIn(
            self.order1,
            self.env["pos.order"].search([("debt_state", "=", "settled")]),
        )

    def test_draft_allocation_does_not_change_accounting(self):
        payment = self._create_incoming_payment(30)
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 30}
        )

        self.assertEqual(self.order1.debt_residual_amount, 100)
        self.assertFalse(allocation.partial_reconcile_ids)

    def test_duplicate_and_cross_currency_allocations_are_rejected(self):
        payment = self._create_incoming_payment(30)
        self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 10}
        )
        with self.assertRaises(ValidationError):
            self.env["pos.customer.debt.allocation"].create(
                {"payment_id": payment.id, "order_id": self.order1.id, "amount": 10}
            )

        foreign_payment = self._create_incoming_payment(
            20, currency=self.other_currency
        )
        with self.assertRaises(ValidationError):
            self.env["pos.customer.debt.allocation"].create(
                {
                    "payment_id": foreign_payment.id,
                    "order_id": self.order1.id,
                    "amount": 20,
                }
            )

    def test_payment_cancellation_keeps_ineffective_history(self):
        payment = self._create_incoming_payment(40)
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 40}
        )
        payment.action_post()

        payment.action_cancel()

        self.order1.invalidate_recordset()
        allocation.invalidate_recordset()
        self.assertEqual(self.order1.debt_residual_amount, 100)
        self.assertEqual(allocation.state, "applied")
        self.assertFalse(allocation.is_effective)

    def test_payment_copy_has_no_allocations(self):
        payment = self._create_incoming_payment(20)
        self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 20}
        )

        copied_payment = payment.copy()

        self.assertFalse(copied_payment.pos_debt_allocation_ids)

    def test_applied_payment_cannot_be_deleted_with_history(self):
        payment = self._create_incoming_payment(20)
        self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 20}
        )
        payment.action_post()

        with self.assertRaises(UserError):
            payment.unlink()

    def test_exact_allocation_in_shared_foreign_currency(self):
        self.config = self.other_currency_config
        debt_amount = self.config.pricelist_id._get_product_price(self.product100, 1)
        _session, orders = self._close_orders(
            [
                self._pay_later_order_values("debt-foreign-1", debt=debt_amount),
                self._pay_later_order_values("debt-foreign-2", debt=debt_amount),
            ],
            payment_methods=self.pay_later_pm,
        )
        order1 = orders["debt-foreign-1"]
        order2 = orders["debt-foreign-2"]
        payment = self._create_incoming_payment(70, currency=self.other_currency)
        allocations = self.env["pos.customer.debt.allocation"].create(
            [
                {"payment_id": payment.id, "order_id": order1.id, "amount": 20},
                {"payment_id": payment.id, "order_id": order2.id, "amount": 50},
            ]
        )

        payment.action_post()

        self.assertEqual(order1.debt_residual_amount, debt_amount - 20)
        self.assertEqual(order2.debt_residual_amount, debt_amount - 50)
        self.assertEqual(sum(allocations.mapped("effective_amount")), 70)
        self.assertEqual(payment.pos_debt_available_amount, 0)

    def test_allocation_preserves_cash_basis_tax_processing(self):
        self.company.write(
            {
                "tax_exigibility": True,
                "tax_cash_basis_journal_id": self.company_data[
                    "default_journal_misc"
                ].id,
            }
        )
        transition_account = self.receivable_account.copy(
            {
                "name": "POS Cash Basis Transition",
                "code": "CBPOS",
                "account_type": "asset_current",
                "reconcile": True,
            }
        )
        tax = self.taxes["tax7"]
        tax.write(
            {
                "tax_exigibility": "on_payment",
                "cash_basis_transition_account_id": transition_account.id,
            }
        )
        self.product100.taxes_id = tax
        _session, orders = self._close_orders(
            [self._pay_later_order_values("debt-cash-basis", debt=107)]
        )
        order = orders["debt-cash-basis"]
        payment = self._create_incoming_payment(53.5)
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": order.id, "amount": 53.5}
        )

        payment.action_post()

        cash_basis_move = self.env["account.move"].search(
            [("tax_cash_basis_rec_id", "in", allocation.partial_reconcile_ids.ids)]
        )
        self.assertEqual(order.debt_residual_amount, 53.5)
        self.assertTrue(cash_basis_move)

    def test_invalid_allocations_are_rejected_without_reconciliation(self):
        payment = self._create_incoming_payment(50)
        with self.assertRaises(ValidationError):
            self.env["pos.customer.debt.allocation"].create(
                {"payment_id": payment.id, "order_id": self.order1.id, "amount": 0}
            )
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 60}
        )
        with self.assertRaises(UserError):
            payment.action_post()
        self.assertEqual(self.order1.debt_residual_amount, 100)
        self.assertFalse(allocation.partial_reconcile_ids)

    def test_multiple_allocations_fail_atomically(self):
        payment = self._create_incoming_payment(200)
        allocations = self.env["pos.customer.debt.allocation"].create(
            [
                {"payment_id": payment.id, "order_id": self.order1.id, "amount": 20},
                {"payment_id": payment.id, "order_id": self.order2.id, "amount": 120},
            ]
        )

        with self.assertRaises(UserError):
            payment.action_post()

        self.assertEqual(self.order1.debt_residual_amount, 100)
        self.assertEqual(self.order2.debt_residual_amount, 100)
        self.assertFalse(allocations.partial_reconcile_ids)

    def test_lock_contention_rejects_without_partial_settlement(self):
        payment = self._create_incoming_payment(40)
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 40}
        )
        empty_payment = self.env["account.payment"]

        with patch.object(
            type(payment), "try_lock_for_update", return_value=empty_payment
        ), self.assertRaises(UserError):
            payment.action_post()

        self.assertEqual(self.order1.debt_residual_amount, 100)
        self.assertEqual(allocation.state, "draft")
        self.assertFalse(allocation.partial_reconcile_ids)

    def test_lock_contention_is_detected_between_independent_transactions(self):
        record = self.env.ref("pos_customer_debt.group_pos_customer_debt_viewer")
        self.assertEqual(record.try_lock_for_update(), record)

        with self.env.registry.cursor() as cursor:
            concurrent_record = record.with_env(record.env(cr=cursor))
            self.assertFalse(concurrent_record.try_lock_for_update())

    def test_outgoing_payment_is_rejected_server_side(self):
        payment = self._create_incoming_payment(20)
        payment.payment_type = "outbound"
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 20}
        )

        with self.assertRaises(UserError):
            payment.action_post()

        self.assertEqual(self.order1.debt_residual_amount, 100)
        self.assertFalse(allocation.partial_reconcile_ids)

    def test_cross_company_direct_allocation_is_rejected(self):
        other_company_data = self.setup_other_company()
        other_company = other_company_data["company"]
        self.env.user.write({"company_ids": [Command.link(other_company.id)]})
        journal = other_company_data["default_journal_bank"]
        payment = self.env["account.payment"].with_company(other_company).create(
            {
                "amount": 20,
                "payment_type": "inbound",
                "partner_type": "customer",
                "partner_id": self.customer.id,
                "journal_id": journal.id,
                "payment_method_line_id": journal.inbound_payment_method_line_ids[:1].id,
                "destination_account_id": self.customer.with_company(
                    other_company
                ).property_account_receivable_id.id,
                "date": fields.Date.today(),
            }
        )

        with self.assertRaises(ValidationError):
            self.env["pos.customer.debt.allocation"].create(
                {"payment_id": payment.id, "order_id": self.order1.id, "amount": 20}
            )

    def test_undo_restores_debt_and_applied_values_are_protected(self):
        payment = self._create_incoming_payment(40)
        allocation = self.env["pos.customer.debt.allocation"].create(
            {"payment_id": payment.id, "order_id": self.order1.id, "amount": 40}
        )
        payment.action_post()
        with self.assertRaises(UserError):
            allocation.amount = 30

        allocation.action_undo()
        self.assertEqual(self.order1.debt_residual_amount, 100)
        self.assertEqual(allocation.state, "cancelled")
        self.assertFalse(allocation.is_effective)
