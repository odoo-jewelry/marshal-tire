from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class PosCustomerDebtAllocation(models.Model):
    _name = "pos.customer.debt.allocation"
    _description = "POS Customer Debt Allocation"
    _order = "id desc"

    payment_id = fields.Many2one(
        "account.payment",
        required=True,
        index=True,
        copy=False,
        check_company=True,
        ondelete="restrict",
    )
    order_id = fields.Many2one(
        "pos.order",
        required=True,
        index=True,
        copy=False,
        check_company=True,
        ondelete="restrict",
    )
    company_id = fields.Many2one(
        related="payment_id.company_id",
        store=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related="payment_id.currency_id",
        store=True,
    )
    partner_id = fields.Many2one(
        related="payment_id.partner_id",
        store=True,
        index=True,
    )
    payment_reference = fields.Char(
        related="payment_id.name",
        store=True,
        string="Payment Reference",
    )
    amount = fields.Monetary(required=True, currency_field="currency_id")
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("applied", "Applied"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
    )
    payment_move_line_id = fields.Many2one(
        "account.move.line",
        copy=False,
        check_company=True,
        ondelete="restrict",
    )
    debt_move_line_ids = fields.Many2many(
        "account.move.line",
        "pos_debt_allocation_debt_line_rel",
        "allocation_id",
        "move_line_id",
        copy=False,
        string="Debt Journal Items",
    )
    partial_reconcile_ids = fields.Many2many(
        "account.partial.reconcile",
        "pos_debt_allocation_partial_rel",
        "allocation_id",
        "partial_id",
        copy=False,
        string="Reconciliations",
    )
    effective_amount = fields.Monetary(
        compute="_compute_effective_amount",
        compute_sudo=True,
        currency_field="currency_id",
    )
    is_effective = fields.Boolean(
        compute="_compute_effective_amount",
        compute_sudo=True,
    )
    applied_on = fields.Datetime(copy=False, readonly=True)
    applied_by_id = fields.Many2one("res.users", copy=False, readonly=True)

    @api.depends(
        "state",
        "partial_reconcile_ids.amount",
        "partial_reconcile_ids.debit_amount_currency",
        "partial_reconcile_ids.credit_amount_currency",
        "debt_move_line_ids",
    )
    def _compute_effective_amount(self):
        for allocation in self:
            effective = 0.0
            for partial in allocation.partial_reconcile_ids:
                if partial.debit_move_id in allocation.debt_move_line_ids:
                    effective += partial.debit_amount_currency
                elif partial.credit_move_id in allocation.debt_move_line_ids:
                    effective += partial.credit_amount_currency
            allocation.effective_amount = effective
            allocation.is_effective = (
                allocation.state == "applied"
                and not allocation.currency_id.is_zero(effective)
            )

    @api.constrains("amount", "payment_id", "order_id")
    def _check_draft_values(self):
        for allocation in self:
            if allocation.amount <= 0.0:
                raise ValidationError(self.env._("The allocation amount must be positive."))
            if allocation.payment_id.company_id != allocation.order_id.company_id:
                raise ValidationError(
                    self.env._("The payment and order must belong to the same company.")
                )
            if allocation.payment_id.currency_id != allocation.order_id.currency_id:
                raise ValidationError(
                    self.env._("Cross-currency debt allocation is not supported.")
                )
            payment_partner = allocation.payment_id.partner_id.commercial_partner_id
            order_partner = allocation.order_id.partner_id.commercial_partner_id
            if payment_partner != order_partner:
                raise ValidationError(
                    self.env._("The payment and order must have the same accounting customer.")
                )

    @api.model_create_multi
    def create(self, values_list):
        allocations = super().create(values_list)
        allocations._check_duplicate_draft_orders()
        return allocations

    def write(self, values):
        protected = {
            "payment_id",
            "order_id",
            "amount",
            "payment_move_line_id",
            "debt_move_line_ids",
            "partial_reconcile_ids",
        }
        if protected.intersection(values) and any(
            allocation.state != "draft" for allocation in self
        ):
            raise UserError(
                self.env._(
                    "Applied debt allocations must be undone before they can be changed."
                )
            )
        result = super().write(values)
        if {"payment_id", "order_id"}.intersection(values):
            self._check_duplicate_draft_orders()
        return result

    def unlink(self):
        if any(allocation.state != "draft" for allocation in self):
            raise UserError(
                self.env._(
                    "Applied debt allocations must be undone before they can be deleted."
                )
            )
        return super().unlink()

    def _check_duplicate_draft_orders(self):
        for allocation in self.filtered(lambda item: item.state == "draft"):
            duplicate = self.search_count(
                [
                    ("id", "!=", allocation.id),
                    ("payment_id", "=", allocation.payment_id.id),
                    ("order_id", "=", allocation.order_id.id),
                    ("state", "=", "draft"),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    self.env._("An order can occur only once in a draft allocation.")
                )

    def _check_settlement_rights(self):
        if not self.env.user.has_group(
            "pos_customer_debt.group_pos_customer_debt_viewer"
        ) or not self.env.user.has_group("account.group_account_invoice"):
            raise AccessError(
                self.env._("You are not allowed to settle point-of-sale customer debt.")
            )

    def action_apply(self):
        allocations = self.exists()
        if not allocations:
            return True
        allocations._check_settlement_rights()
        if len(allocations.payment_id) != 1:
            raise UserError(self.env._("Apply allocations for one payment at a time."))
        payment = allocations.payment_id
        drafts = allocations.filtered(lambda allocation: allocation.state == "draft")
        if not drafts:
            return True
        if allocations != drafts:
            raise UserError(self.env._("Draft and applied allocations cannot be mixed."))

        locked_payment = payment.try_lock_for_update()
        locked_allocations = drafts.sorted("id").try_lock_for_update()
        if locked_payment != payment or locked_allocations != drafts.sorted("id"):
            raise UserError(
                self.env._(
                    "The debt allocation changed concurrently. Refresh and try again."
                )
            )

        payment.invalidate_recordset()
        drafts.invalidate_recordset()
        if payment.payment_type != "inbound" or payment.partner_type != "customer":
            raise UserError(self.env._("Only incoming customer payments can settle debt."))
        if payment.state not in ("in_process", "paid") or not payment.move_id:
            raise UserError(self.env._("Post the incoming payment before allocating it."))
        if payment.move_id.state != "posted":
            raise UserError(self.env._("The payment journal entry must be posted."))

        drafts.order_id._check_debt_orders_compatible()
        counterpart_lines = payment._get_pos_debt_counterpart_lines()
        debt_lines = drafts.order_id.mapped("debt_source_line_ids")
        locked_lines = (counterpart_lines | debt_lines).sorted("id").try_lock_for_update()
        if locked_lines != (counterpart_lines | debt_lines).sorted("id"):
            raise UserError(
                self.env._("A debt balance changed concurrently. Refresh and try again.")
            )
        (counterpart_lines | debt_lines).invalidate_recordset()
        drafts.order_id.invalidate_recordset()

        payment_account = counterpart_lines.account_id
        if len(payment_account) != 1:
            raise UserError(
                self.env._("The payment must have one available receivable account.")
            )
        if drafts.order_id.mapped("debt_source_line_ids.account_id") != payment_account:
            raise UserError(
                self.env._("The payment and selected debt use different receivable accounts.")
            )

        available = sum(
            max(-line.amount_residual_currency, 0.0) for line in counterpart_lines
        )
        requested = sum(drafts.mapped("amount"))
        if payment.currency_id.compare_amounts(requested, available) > 0:
            raise UserError(
                self.env._("The allocations exceed the available payment amount.")
            )
        for allocation in drafts:
            if allocation.order_id.debt_state != "outstanding":
                raise UserError(
                    self.env._("Only current outstanding debts can be allocated.")
                )
            if payment.currency_id.compare_amounts(
                allocation.amount, allocation.order_id.debt_residual_amount
            ) > 0:
                raise UserError(
                    self.env._("An allocation exceeds the order's current debt.")
                )

        for allocation in drafts.sorted("id"):
            remaining = allocation.amount
            allocation_debt_lines = allocation.order_id.debt_source_line_ids.filtered(
                lambda line: line.amount_residual_currency > 0.0
                and line.account_id == payment_account
            ).sorted(lambda line: (line.date_maturity or line.date, line.id))
            created_partials = self.env["account.partial.reconcile"]
            used_debt_lines = self.env["account.move.line"]
            used_payment_line = self.env["account.move.line"]
            for debt_line in allocation_debt_lines:
                for payment_line in counterpart_lines.filtered(
                    lambda line: line.amount_residual_currency < 0.0
                ):
                    amount = min(
                        remaining,
                        debt_line.amount_residual_currency,
                        -payment_line.amount_residual_currency,
                    )
                    if payment.currency_id.is_zero(amount):
                        continue
                    before = debt_line.matched_credit_ids | payment_line.matched_debit_ids
                    (debt_line | payment_line).with_context(
                        pos_customer_debt_reconcile_amount=amount
                    )._reconcile_plan([debt_line | payment_line])
                    after = debt_line.matched_credit_ids | payment_line.matched_debit_ids
                    created_partials |= after - before
                    used_debt_lines |= debt_line
                    used_payment_line |= payment_line
                    remaining -= amount
                    if payment.currency_id.is_zero(remaining):
                        break
                if payment.currency_id.is_zero(remaining):
                    break
            if not payment.currency_id.is_zero(remaining):
                raise UserError(
                    self.env._("The current residual amounts cannot satisfy the allocation.")
                )
            effective = sum(
                partial.debit_amount_currency
                if partial.debit_move_id in used_debt_lines
                else partial.credit_amount_currency
                for partial in created_partials
            )
            if payment.currency_id.compare_amounts(effective, allocation.amount) != 0:
                raise UserError(
                    self.env._("The accounting reconciliation did not match the requested amount.")
                )
            allocation.with_context(pos_customer_debt_applying=True).write(
                {
                    "state": "applied",
                    "payment_move_line_id": used_payment_line.id,
                    "debt_move_line_ids": [(6, 0, used_debt_lines.ids)],
                    "partial_reconcile_ids": [(6, 0, created_partials.ids)],
                    "applied_on": fields.Datetime.now(),
                    "applied_by_id": self.env.user.id,
                }
            )
        return True

    def action_undo(self):
        self._check_settlement_rights()
        for allocation in self:
            if allocation.state != "applied":
                continue
            allocation.partial_reconcile_ids.unlink()
            allocation.with_context(pos_customer_debt_applying=True).write(
                {"state": "cancelled"}
            )
        return True
