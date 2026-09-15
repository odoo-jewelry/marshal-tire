from odoo import Command, api, models
from odoo.exceptions import UserError

from .utils import CORRECTION_INTERNAL_TOKEN, is_internal_correction_call


class PosSession(models.Model):
    _inherit = "pos.session"

    def write(self, vals):
        if "move_id" in vals and not is_internal_correction_call(self.env):
            orders = self.order_ids
            if orders.filtered("is_correction_order") or orders.correction_ids.filtered(
                lambda correction: correction.state == "applied"
            ):
                raise UserError(self.env._("The accounting entry of a corrected POS session cannot be replaced."))
        return super().write(vals)

    def _apply_customer_account_refunds(self, pay_later_lines):
        pay_later_lines = pay_later_lines or self.env["account.move.line"]
        correction_lines = pay_later_lines.filtered(
            lambda line: (
                line.pos_debt_payment_id.pos_order_id.is_correction_order
                or line.pos_debt_payment_id.pos_order_id.correction_return_root_id
            )
        )
        result = super()._apply_customer_account_refunds(pay_later_lines - correction_lines)
        credit_lines = correction_lines.filtered(
            lambda line: line.pos_debt_payment_id.amount < 0.0 and not line.reconciled
        )
        for credit_line in credit_lines:
            order = credit_line.pos_debt_payment_id.pos_order_id
            root = order.correction_root_id or order.correction_return_root_id
            source_lines = root._get_effective_debt_source_lines().filtered(
                lambda line: line.id != credit_line.id
                and line.account_id == credit_line.account_id
                and line.currency_id == credit_line.currency_id
                and line.amount_residual_currency > 0.0
            )
            remaining = abs(credit_line.amount_residual_currency)
            for debit_line in source_lines.sorted(
                lambda line: (line.date_maturity or line.date, line.id)
            ):
                amount = min(remaining, debit_line.amount_residual_currency)
                if credit_line.currency_id.is_zero(amount):
                    break
                (debit_line | credit_line).with_context(
                    pos_customer_debt_reconcile_amount=amount
                )._reconcile_plan([debit_line | credit_line])
                remaining -= amount
        corrections = credit_lines.mapped("pos_debt_payment_id.pos_order_id.correction_id")
        for correction in corrections:
            lines = correction.applied_order_id.payment_ids.debt_move_line_ids
            partials = lines.matched_debit_ids | lines.matched_credit_ids
            correction.with_context(
                pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
            ).write(
                {"internal_partial_reconcile_ids": [Command.set(partials.ids)]}
            )
        return result

    def _validate_session(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        self.ensure_one()
        if self.try_lock_for_update() != self:
            raise UserError(self.env._("The POS session is being processed. Try again."))
        self.invalidate_recordset()
        roots = self.order_ids.mapped(lambda order: order._get_correction_root())
        if roots:
            roots._lock_correction_chain()
        return super(PosSession, self.with_context(
            pos_order_correction_internal=CORRECTION_INTERNAL_TOKEN
        ))._validate_session(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )


class PosOrderDebt(models.Model):
    _inherit = "pos.order"

    def _check_correction_eligibility(self):
        result = super()._check_correction_eligibility()
        for root in self:
            closed_orders = root._get_correction_chain().filtered(
                lambda order: order.session_id.state == "closed"
            )
            for order in closed_orders:
                payments = order.payment_ids.filtered(
                    lambda payment: not order.currency_id.is_zero(payment.amount)
                )
                session_move = order.session_id.move_id
                if (payments or not order.currency_id.is_zero(order.amount_total)) and session_move.state != "posted":
                    raise UserError(self.env._("The closed POS sale has no unambiguous posted accounting source."))
                for payment in payments.filtered(lambda item: item.payment_method_id.type == "pay_later"):
                    source = payment.debt_move_line_ids
                    if len(source) != 1:
                        raise UserError(self.env._("The closed POS sale has no unambiguous posted accounting source."))
                    # Validate provenance against the native posting values,
                    # without interpreting residuals or internal settlements.
                    expected = order.session_id.with_company(order.company_id)._get_split_receivable_vals(
                        payment.with_company(order.company_id), payment.amount, source.balance
                    )
                    if (
                        source.move_id != session_move or source.parent_state != "posted"
                        or source.company_id != order.company_id
                        or source.currency_id != order.currency_id
                        or source.account_id.account_type != "asset_receivable"
                        or source.account_id.id != expected["account_id"]
                        or source.partner_id.id != expected["partner_id"]
                        or order.currency_id.compare_amounts(source.amount_currency, payment.amount)
                    ):
                        raise UserError(self.env._("The closed POS sale has no unambiguous posted accounting source."))
        return result

    @api.depends(
        "correction_ids.state",
        "correction_ids.applied_order_id.session_id.state",
        "correction_ids.applied_order_id.payment_ids.amount",
        "correction_ids.applied_order_id.payment_ids.debt_move_line_ids.amount_residual_currency",
        "correction_ids.applied_order_id.payment_ids.debt_move_line_ids.matched_debit_ids",
        "correction_ids.applied_order_id.payment_ids.debt_move_line_ids.matched_credit_ids",
    )
    def _compute_customer_debt(self):
        super()._compute_customer_debt()
        for order in self.filtered(lambda item: not item.is_correction_order):
            if not order.correction_ids.filtered(lambda correction: correction.state == "applied"):
                continue
            historical_debt = sum(order.payment_ids.filtered(
                lambda payment: payment.payment_method_id.type == "pay_later" and payment.amount > 0.0
            ).mapped("amount"))
            order.debt_original_amount = historical_debt
            # Positive adjustments reduce the original debt; negative ones add
            # debt. Keep the historical principal and actual payments distinct.
            order.debt_adjustment_amount = order.currency_id.round(
                historical_debt - order.debt_residual_amount - order.debt_payment_amount
            )

    def _get_customer_account_payments(self):
        self.ensure_one()
        if self.env.context.get("pos_order_correction_own_payments") is CORRECTION_INTERNAL_TOKEN:
            return super()._get_customer_account_payments()
        if self.env.context.get("pos_order_correction_defer_debt_reconcile") is CORRECTION_INTERNAL_TOKEN:
            return self.env["pos.payment"]
        root = self._get_correction_root()
        if root != self:
            return self.env["pos.payment"]
        return root._get_correction_chain().payment_ids.filtered(
            lambda payment: payment.payment_method_id.type == "pay_later"
        )

    def _get_effective_debt_source_lines(self):
        self.ensure_one()
        root = self._get_correction_root()
        chain = root._get_correction_chain()
        if len(chain) == 1:
            return super()._get_effective_debt_source_lines()
        if chain.mapped("account_move"):
            return super(PosOrderDebt, root)._get_effective_debt_source_lines()
        payments = chain.payment_ids.filtered(
            lambda payment: payment.payment_method_id.type == "pay_later"
            and payment.amount > 0.0
        )
        return payments.debt_move_line_ids.filtered(
            lambda line: line.parent_state == "posted"
            and line.account_id.account_type == "asset_receivable"
            and line.balance > 0.0
        )

    @api.model
    def _get_debt_candidate_orders(self):
        candidates = super()._get_debt_candidate_orders()
        return (candidates | candidates.correction_root_id).filtered(
            lambda order: not order.is_correction_order
        )

    def _check_debt_orders_compatible(self):
        if self.filtered("is_correction_order"):
            raise UserError(self.env._("Settle the debt from the original POS order."))
        if any(order.correction_pending for order in self):
            raise UserError(
                self.env._("Close all correction sessions before settling this debt.")
            )
        return super()._check_debt_orders_compatible()

    def _prepare_aml_values_list_per_nature(self):
        return super(PosOrderDebt, self.with_context(
            pos_order_correction_own_payments=CORRECTION_INTERNAL_TOKEN
        ))._prepare_aml_values_list_per_nature()

    def _create_misc_reversal_move(self, payment_moves):
        if self.env.context.get("pos_order_correction_invoice_token") is CORRECTION_INTERNAL_TOKEN:
            # Transfer receivables after every reversal exists. A credit from an
            # earlier correction must offset its chain, not the new invoice.
            self = self.with_context(
                pos_order_correction_defer_debt_reconcile=CORRECTION_INTERNAL_TOKEN
            )
        return super(PosOrderDebt, self)._create_misc_reversal_move(payment_moves)

    def _reconcile_correction_invoice_debt(self, invoice):
        source_lines = self.payment_ids.debt_move_line_ids.filtered(
            lambda line: line.parent_state == "posted" and not line.reconciled
        )
        for lines in source_lines.grouped(
            lambda line: (line.account_id, line.currency_id, line.partner_id)
        ).values():
            lines.reconcile()
            remainder = lines.filtered(lambda line: not line.reconciled)
            invoice_lines = invoice.line_ids.filtered(
                lambda line: line.account_id == lines.account_id
                and line.currency_id == lines.currency_id
                and not line.reconciled
            )
            if remainder and invoice_lines:
                (remainder | invoice_lines).reconcile()
