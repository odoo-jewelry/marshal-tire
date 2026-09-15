from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .common import PosOrderCorrectionCommon


@tagged("post_install", "-at_install")
class TestPosOrderCorrectionSecurity(PosOrderCorrectionCommon):
    def test_cashier_cannot_prepare_correction(self):
        order = self._create_paid_order("correction-security-1")
        cashier = new_test_user(
            self.env,
            login="pos_correction_cashier",
            groups="point_of_sale.group_pos_user",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )

        with self.assertRaises(AccessError):
            order.with_user(cashier).action_prepare_correction()

    def test_applied_records_are_immutable(self):
        order = self._create_paid_order("correction-security-2")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 110
        correction.payment_ids.amount = 110
        correction.reason = "Wrong price"
        correction.action_apply()
        difference_order = correction.applied_order_id

        with self.assertRaises(UserError):
            correction.write({"reason": "Changed later"})
        with self.assertRaises(UserError):
            correction.copy()
        with self.assertRaises(UserError):
            correction.line_ids.write({"qty": 2})
        with self.assertRaises(UserError):
            difference_order.lines.write({"price_unit": 1})
        with self.assertRaises(UserError):
            difference_order.payment_ids.write({"amount": 1})
        with self.assertRaises(UserError):
            difference_order.write({"amount_total": 1})
        with self.assertRaises(UserError):
            difference_order.with_context(
                pos_order_correction_internal=True
            ).write({"amount_total": 1})
        with self.assertRaises(UserError):
            difference_order.action_pos_order_cancel()
        with self.assertRaises(UserError):
            difference_order.copy()
        with self.assertRaises(UserError):
            difference_order.unlink()

    def test_stale_draft_is_rejected(self):
        order = self._create_paid_order("correction-security-3")
        first = self._prepare(order)
        stale = first.copy(
            {
                "revision": first.revision + 1,
                "request_key": "stale-correction-request",
                "reason": "Stale preparation",
            }
        )
        first.line_ids.price_unit = 110
        first.payment_ids.amount = 110
        first.reason = "First correction"
        first.action_apply()

        with self.assertRaises(UserError):
            stale.action_apply()

    def test_closed_target_session_is_rejected(self):
        order = self._create_paid_order("correction-security-4")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 110
        correction.payment_ids.amount = 110
        correction.reason = "Wrong price"
        self._close_session(self.session)

        with self.assertRaises(UserError):
            correction.action_apply()

    def test_invalid_values_and_foreign_source_are_rejected(self):
        first_order = self._create_paid_order("correction-security-5")
        second_order = self._create_paid_order("correction-security-6")
        correction = self._prepare(first_order)
        correction.reason = "Invalid values"
        correction.line_ids.discount = 101
        with self.assertRaises(ValidationError):
            correction.action_apply()

        correction.line_ids.discount = 0
        correction.line_ids.source_order_line_id = second_order.lines
        with self.assertRaises(ValidationError):
            correction.action_apply()

    def test_batch_failure_rolls_back_first_correction(self):
        first_order = self._create_paid_order("correction-security-7")
        second_order = self._create_paid_order("correction-security-8")
        first = self._prepare(first_order)
        first.line_ids.price_unit = 110
        first.payment_ids.amount = 110
        first.reason = "Valid correction"
        second = self._prepare(second_order)
        second.line_ids.price_unit = 120
        second.reason = "Unmatched payment"

        with self.assertRaises(UserError):
            (first | second).action_apply()
        first.invalidate_recordset()
        second.invalidate_recordset()
        self.assertEqual(first.state, "draft")
        self.assertFalse(first.applied_order_id)
        self.assertFalse(first_order.correction_order_ids)

    def test_applied_children_cannot_be_created_or_reparented(self):
        order = self._create_paid_order("correction-security-children")
        applied = self._prepare(order)
        applied.line_ids.price_unit = 110
        applied.payment_ids.amount = 110
        applied.reason = "Fix price"
        applied.action_apply()
        draft = self._prepare(order)

        for model_name, values in (
            ("pos.order.correction.line", {"product_id": self.product100.id, "qty": 1, "price_unit": 1}),
            ("pos.order.correction.payment", {"payment_method_id": self.bank_pm1.id, "amount": 1}),
        ):
            model = self.env[model_name]
            with self.subTest(model=model_name, operation="create"):
                with self.assertRaises(UserError):
                    model.create({**values, "correction_id": applied.id})
            with self.subTest(model=model_name, operation="context default"):
                with self.assertRaises(UserError):
                    model.with_context(default_correction_id=applied.id).create(values)
        for child in (draft.line_ids, draft.payment_ids):
            with self.assertRaises(UserError):
                child.write({"correction_id": applied.id})
        with self.assertRaises(UserError):
            draft.line_ids.with_context(pos_order_correction_internal=True).write(
                {"result_order_line_id": order.lines.id}
            )

    def test_operational_children_cannot_be_added_or_reparented(self):
        order = self._create_paid_order("correction-security-operational")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 110
        correction.payment_ids.amount = 110
        correction.reason = "Fix price"
        correction.action_apply()
        difference = correction.applied_order_id
        with self.assertRaises(UserError):
            self.env["pos.order.line"].create({
                "order_id": difference.id, "product_id": self.product100.id,
                "qty": 1, "price_unit": 1, "price_subtotal": 1,
                "price_subtotal_incl": 1,
            })
        with self.assertRaises(UserError):
            self.env["pos.payment"].create({
                "pos_order_id": difference.id, "payment_method_id": self.cash_pm1.id,
                "amount": 1,
            })
        with self.assertRaises(UserError):
            order.lines.write({"order_id": difference.id})
        with self.assertRaises(UserError):
            order.payment_ids.write({"pos_order_id": difference.id})
        with self.assertRaises(UserError):
            order.lines.with_context(pos_order_correction_internal=True).write(
                {"correction_origin_line_id": difference.lines[0].id}
            )

    def test_import_cannot_forge_application_results(self):
        order = self._create_paid_order("correction-security-import")
        correction = self._prepare(order)
        values = {
            "root_order_id": order.id, "revision": 2, "base_revision": 0,
            "target_session_id": self.session.id,
        }
        with self.assertRaises(UserError):
            self.env["pos.order.correction"].create({**values, "applied_order_id": order.id})
        with self.assertRaises(UserError):
            self.env["pos.order.correction"].with_context(default_state="applied").create(values)
        with self.assertRaises(UserError):
            correction.with_context(pos_order_correction_internal=True).write(
                {"state": "applied"}
            )
        self.assertEqual(correction.state, "draft")

    def test_duplicate_source_is_rejected(self):
        order = self._create_paid_order("correction-security-duplicate")
        correction = self._prepare(order)
        self.env["pos.order.correction.line"].create({
            "correction_id": correction.id, "source_order_line_id": order.lines.id,
            "product_id": self.product100.id, "qty": 1, "price_unit": 100,
        })
        correction.reason = "Duplicate source"
        correction.payment_ids.amount = 200
        with self.assertRaises(ValidationError):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)

    def test_non_finite_values_are_rejected(self):
        order = self._create_paid_order("correction-security-finite")
        correction = self._prepare(order)
        correction.reason = "Invalid number"
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                correction.line_ids.price_unit = value
                with self.assertRaises(ValidationError):
                    correction.action_apply()
                self.assertFalse(correction.applied_order_id)
        correction.line_ids.price_unit = 100

    def test_source_child_change_invalidates_preparation(self):
        order = self._create_paid_order("correction-security-snapshot")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 110
        correction.payment_ids.amount = 110
        correction.reason = "Fix price"
        order.payment_ids.transaction_id = "Evidence received after preparation"
        with self.assertRaisesRegex(UserError, "source sale changed"):
            correction.action_apply()
        self.assertFalse(correction.applied_order_id)

    def test_foreign_company_product_is_rejected_on_draft_write(self):
        order = self._create_paid_order("correction-security-company")
        correction = self._prepare(order)
        foreign_company = self.env["res.company"].create({"name": "Foreign correction company"})
        foreign_product = self.env["product.product"].with_company(foreign_company).create({
            "name": "Foreign correction product", "company_id": foreign_company.id,
            "available_in_pos": True,
        })
        with self.assertRaises(UserError), self.cr.savepoint():
            correction.line_ids.with_context(
                allowed_company_ids=(self.env.company | foreign_company).ids,
            ).write({"product_id": foreign_product.id})
        self.assertEqual(correction.line_ids.product_id, self.product100)

    def test_correction_permission_does_not_grant_stock_move_line_access(self):
        order = self._create_paid_order("correction-security-stock-rights")
        correction = self._prepare(order)
        correction.line_ids.product_id = self.product80
        correction.line_ids.price_unit = 80
        correction.payment_ids.amount = 80
        correction.reason = "Replace product"
        restricted = new_test_user(
            self.env, login="pos_correction_without_stock_rights",
            groups="pos_order_correction.group_pos_order_correction,account.group_account_readonly",
            company_id=self.env.company.id,
            company_ids=[Command.set(self.env.company.ids)],
        )
        # Standard stock grants move-line rights to every internal user. Model
        # an installation with those broad rights removed, without changing groups.
        stock_access = self.env["ir.model.access"].search([
            ("model_id.model", "=", "stock.move.line"),
            "|", ("group_id", "=", False), ("group_id", "in", restricted.all_group_ids.ids),
        ])
        stock_access.write({
            "perm_create": False, "perm_write": False,
        })
        with self.assertRaises(AccessError):
            self.env["stock.move.line"].with_user(restricted).check_access("create")
        with self.assertRaises(AccessError):
            correction.with_user(restricted).action_apply()
        self.assertEqual(correction.state, "draft")
        self.assertFalse(correction.applied_order_id)

    def test_completed_stock_effects_cannot_be_rewritten(self):
        order = self._create_paid_order("correction-security-stock-history")
        correction = self._prepare(order)
        correction.line_ids.product_id = self.product80
        correction.line_ids.price_unit = 80
        correction.payment_ids.amount = 80
        correction.reason = "Replace product"
        correction.action_apply()
        moves = correction.applied_order_id.picking_ids.move_ids
        self.assertTrue(moves)
        for move in moves:
            with self.assertRaises(UserError):
                move.with_context(pos_order_correction_internal=True).write({"quantity": 2})
            with self.assertRaises(UserError):
                move.copy()
            with self.assertRaises(UserError):
                move.move_line_ids.write({"quantity": 2})
        with self.assertRaises(UserError):
            correction.applied_order_id.picking_ids[:1].copy()

    def test_correction_accounting_cannot_be_reset_or_rewritten(self):
        order = self._create_paid_order("correction-security-accounting-history")
        correction = self._prepare(order)
        correction.line_ids.price_unit = 110
        correction.payment_ids.amount = 110
        correction.reason = "Fix price"
        correction.action_apply()
        self._close_session(self.session)
        entry = self.session.move_id
        self.assertEqual(entry.state, "posted")
        with self.assertRaises(UserError):
            entry.button_draft()
        with self.assertRaises(UserError):
            entry.copy()
        with self.assertRaises(UserError):
            entry.line_ids[:1].with_context(pos_order_correction_internal=True).write({"balance": 1})

    def test_removed_external_matching_still_blocks_correction(self):
        order = self._create_paid_order("correction-security-matching-history", self.pay_later_pm)
        self._close_session(self.session)
        debt_line = order._get_effective_debt_source_lines()
        journal = self.company_data["default_journal_bank"]
        payment_entry = self.env["account.move"].create({
            "journal_id": journal.id,
            "line_ids": [
                Command.create({"name": "Payment", "account_id": journal.default_account_id.id, "debit": 20}),
                Command.create({"name": "Customer", "account_id": debt_line.account_id.id,
                                "partner_id": self.customer.id, "credit": 20}),
            ],
        })
        payment_entry.action_post()
        credit = payment_entry.line_ids.filtered(lambda line: line.account_id == debt_line.account_id)
        (debt_line | credit).reconcile()
        self.assertTrue(order.correction_has_external_settlement)
        (debt_line.matched_debit_ids | debt_line.matched_credit_ids).unlink()
        self.assertEqual(order.debt_residual_amount, 100)
        with self.assertRaisesRegex(UserError, "subsequent debt settlement"):
            order.action_prepare_correction()
        with self.assertRaises(UserError):
            order.write({"correction_has_external_settlement": False})
