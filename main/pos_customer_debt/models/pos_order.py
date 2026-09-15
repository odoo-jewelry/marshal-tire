from odoo import api, fields, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    debt_accounting_partner_id = fields.Many2one(
        related="partner_id.commercial_partner_id",
        store=True,
        index=True,
        string="Accounting Customer",
    )
    debt_source_line_ids = fields.Many2many(
        "account.move.line",
        compute="_compute_customer_debt",
        compute_sudo=True,
        string="Debt Journal Items",
    )
    debt_history_partial_ids = fields.Many2many(
        "account.partial.reconcile",
        compute="_compute_customer_debt",
        compute_sudo=True,
        string="Debt Reconciliations",
    )
    debt_allocation_ids = fields.One2many(
        "pos.customer.debt.allocation",
        "order_id",
        string="Debt Allocations",
        readonly=True,
    )
    debt_original_amount = fields.Monetary(
        compute="_compute_customer_debt",
        compute_sudo=True,
        string="Original Customer Account Debt",
        currency_field="currency_id",
    )
    debt_payment_amount = fields.Monetary(
        compute="_compute_customer_debt",
        compute_sudo=True,
        string="Settled by Payments",
        currency_field="currency_id",
    )
    debt_adjustment_amount = fields.Monetary(
        compute="_compute_customer_debt",
        compute_sudo=True,
        string="Other Adjustments",
        currency_field="currency_id",
    )
    debt_residual_amount = fields.Monetary(
        compute="_compute_customer_debt",
        compute_sudo=True,
        search="_search_debt_residual_amount",
        string="Outstanding Customer Account Debt",
        currency_field="currency_id",
    )
    debt_residual_known = fields.Boolean(
        compute="_compute_customer_debt",
        compute_sudo=True,
        string="Outstanding Amount Is Known",
    )
    debt_state = fields.Selection(
        [
            ("not_applicable", "Not Applicable"),
            ("pending_session", "Pending Session Closure"),
            ("outstanding", "Outstanding"),
            ("settled", "Settled"),
            ("review_required", "Review Required"),
        ],
        compute="_compute_customer_debt",
        compute_sudo=True,
        search="_search_debt_state",
        string="Debt Status",
    )
    debt_review_reason = fields.Char(
        compute="_compute_customer_debt",
        compute_sudo=True,
        string="Debt Review Reason",
    )

    def _get_customer_account_payments(self):
        self.ensure_one()
        return self.payment_ids.filtered(
            lambda payment: payment.payment_method_id.type == "pay_later"
        )

    def _get_session_debt_source_lines(self):
        self.ensure_one()
        payments = self._get_customer_account_payments().filtered(
            lambda payment: payment.amount > 0.0
        )
        return payments.debt_move_line_ids.filtered(
            lambda line: line.parent_state == "posted"
            and line.account_id.account_type == "asset_receivable"
            and line.balance > 0.0
        )

    def _get_effective_debt_source_lines(self):
        self.ensure_one()
        if self.session_id.state != "closed" or self.state == "cancel":
            return self.env["account.move.line"]
        if self.account_move and self.account_move.state == "posted":
            accounting_partner = self.env["res.partner"]._find_accounting_partner(
                self.partner_id
            )
            return self.account_move.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
                and line.partner_id.commercial_partner_id == accounting_partner
                and line.balance > 0.0
            )
        return self._get_session_debt_source_lines()

    def _get_debt_history_partials(self, source_lines):
        self.ensure_one()
        partials = source_lines.matched_debit_ids | source_lines.matched_credit_ids
        partials |= self.debt_allocation_ids.partial_reconcile_ids
        return partials

    @api.depends(
        "payment_ids.amount",
        "payment_ids.payment_method_id",
        "payment_ids.debt_move_line_ids.amount_residual_currency",
        "payment_ids.debt_move_line_ids.matched_debit_ids",
        "payment_ids.debt_move_line_ids.matched_credit_ids",
        "account_move.state",
        "account_move.line_ids.amount_residual_currency",
        "account_move.line_ids.matched_debit_ids",
        "account_move.line_ids.matched_credit_ids",
        "debt_allocation_ids.partial_reconcile_ids",
        "session_id.state",
        "state",
    )
    def _compute_customer_debt(self):
        for order in self:
            customer_payments = order._get_customer_account_payments()
            positive_payments = customer_payments.filtered(
                lambda payment: payment.amount > 0.0
            )
            original = sum(positive_payments.mapped("amount"))
            source_lines = order._get_effective_debt_source_lines()
            history_partials = order._get_debt_history_partials(source_lines)
            residual = sum(
                max(line.amount_residual_currency, 0.0) for line in source_lines
            )
            effective_allocations = order.debt_allocation_ids.filtered(
                "is_effective"
            )
            allocated_partial_ids = set(effective_allocations.partial_reconcile_ids.ids)
            direct_payment_partials = history_partials.filtered(
                lambda partial: partial.id not in allocated_partial_ids
                and (
                    partial.debit_move_id.move_id.origin_payment_id
                    or partial.credit_move_id.move_id.origin_payment_id
                )
            )
            payment_amount = sum(effective_allocations.mapped("effective_amount"))
            for partial in direct_payment_partials:
                if partial.debit_move_id in source_lines:
                    payment_amount += partial.debit_amount_currency
                elif partial.credit_move_id in source_lines:
                    payment_amount += partial.credit_amount_currency

            order.debt_source_line_ids = source_lines
            order.debt_history_partial_ids = history_partials
            order.debt_original_amount = original
            order.debt_residual_amount = residual
            order.debt_residual_known = bool(source_lines)
            order.debt_payment_amount = min(payment_amount, original)
            order.debt_adjustment_amount = max(
                original - residual - order.debt_payment_amount, 0.0
            )
            order.debt_review_reason = False

            ambiguous_refund = (
                any(payment.amount < 0.0 for payment in customer_payments)
                and len(order.lines.refunded_orderline_id.order_id) != 1
            )
            if not original:
                order.debt_state = (
                    "review_required" if ambiguous_refund else "not_applicable"
                )
                if ambiguous_refund:
                    order.debt_review_reason = self.env._(
                        "The customer-account refund has no unique source order."
                    )
            elif order.session_id.state != "closed":
                order.debt_state = "pending_session"
            elif not order.partner_id:
                order.debt_state = "review_required"
                order.debt_review_reason = self.env._(
                    "The order has no identified customer."
                )
            elif not source_lines:
                order.debt_state = "review_required"
                order.debt_review_reason = self.env._(
                    "No unambiguous posted receivable journal item is linked to the order."
                )
            elif order.currency_id.is_zero(residual):
                order.debt_state = "settled"
            else:
                order.debt_state = "outstanding"

    @api.model
    def _get_debt_candidate_orders(self):
        payment_methods = self.env["pos.payment.method"].sudo().search([]).filtered(
            lambda method: method.type == "pay_later"
        )
        return self.search(
            [
                ("payment_ids.payment_method_id", "in", payment_methods.ids),
                ("state", "!=", "cancel"),
                ("company_id", "in", self.env.companies.ids),
            ]
        )

    def _search_debt_state(self, operator, value):
        candidates = self._get_debt_candidate_orders()
        expected = set(value) if operator in ("in", "not in") else {value}
        matching = candidates.filtered(
            lambda order: (order.debt_state in expected)
            == (operator not in ("!=", "not in"))
        )
        return [("id", "in", matching.ids)]

    def _search_debt_residual_amount(self, operator, value):
        candidates = self._get_debt_candidate_orders()
        matching = candidates.filtered(
            lambda order: order._matches_debt_amount(operator, value)
        )
        return [("id", "in", matching.ids)]

    def _matches_debt_amount(self, operator, value):
        self.ensure_one()
        amount = self.debt_residual_amount
        return {
            "=": amount == value,
            "!=": amount != value,
            ">": amount > value,
            ">=": amount >= value,
            "<": amount < value,
            "<=": amount <= value,
        }.get(operator, False)

    def action_register_debt_payment(self):
        orders = self.exists()
        orders._check_debt_orders_compatible()
        lines = orders.mapped("debt_source_line_ids").filtered(
            lambda line: line.amount_residual_currency > 0.0
        )
        return {
            "name": self.env._("Register Debt Payment"),
            "type": "ir.actions.act_window",
            "res_model": "account.payment.register",
            "view_mode": "form",
            "view_id": self.env.ref("account.view_account_payment_register_form").id,
            "target": "new",
            "context": {
                "active_model": "account.move.line",
                "active_ids": lines.ids,
                "pos_customer_debt_order_ids": orders.ids,
            },
        }

    def _check_debt_orders_compatible(self):
        if not self:
            raise UserError(self.env._("Select at least one customer debt."))
        self.check_access("read")
        if any(order.debt_state != "outstanding" for order in self):
            raise UserError(
                self.env._("Only unambiguous debts from closed sessions can be settled.")
            )
        accounting_partners = self.mapped("partner_id.commercial_partner_id")
        accounts = self.mapped("debt_source_line_ids.account_id")
        if (
            len(self.company_id) != 1
            or len(self.currency_id) != 1
            or len(accounting_partners) != 1
            or len(accounts) != 1
        ):
            raise UserError(
                self.env._(
                    "Selected debts must use one company, customer, currency, and receivable account."
                )
            )

    def _prepare_aml_values_list_per_nature(self):
        values_by_nature = super()._prepare_aml_values_list_per_nature()
        for payment in self._get_customer_account_payments():
            account = self.partner_id.with_company(
                self.company_id
            ).property_account_receivable_id
            candidates = [
                values
                for values in values_by_nature["payment_terms"]
                if not values.get("pos_debt_payment_id")
                and values.get("account_id") == account.id
                and values.get("partner_id") == self.partner_id.commercial_partner_id.id
                and self.currency_id.compare_amounts(
                    values.get("amount_currency", 0.0), payment.amount
                )
                == 0
            ]
            if candidates:
                candidates[0]["pos_debt_payment_id"] = payment.id
        return values_by_nature

    def _create_misc_reversal_move(self, payment_moves):
        before_ids = self.env["account.move"].search(
            [("reversed_pos_order_id", "=", self.id)]
        ).ids
        result = super(
            PosOrder,
            self.with_context(pos_customer_debt_invoice_order_id=self.id),
        )._create_misc_reversal_move(payment_moves)
        reversal = self.env["account.move"].search(
            [
                ("reversed_pos_order_id", "=", self.id),
                ("id", "not in", before_ids),
            ],
            order="id desc",
            limit=1,
        )
        for payment in self._get_customer_account_payments().filtered(
            lambda candidate: candidate.amount > 0.0
        ):
            source_lines = payment.debt_move_line_ids.filtered(
                lambda line: not line.reconciled
            )
            reversal_lines = reversal.line_ids.filtered(
                lambda line: line.pos_debt_payment_id == payment
                and line.amount_residual_currency < 0.0
            )
            for source_line in source_lines:
                matching_reversal = reversal_lines.filtered(
                    lambda line: line.account_id == source_line.account_id
                    and line.currency_id == source_line.currency_id
                    and not line.reconciled
                )[:1]
                if matching_reversal:
                    (source_line | matching_reversal).reconcile()

            invoice_lines = self.account_move.line_ids.filtered(
                lambda line: line.account_id == payment.partner_id.with_company(
                    self.company_id
                ).property_account_receivable_id
                and line.amount_residual_currency > 0.0
            )
            remaining_reversal = reversal_lines.filtered(
                lambda line: line.amount_residual_currency < 0.0
            )
            if invoice_lines and remaining_reversal:
                (invoice_lines | remaining_reversal).reconcile()
        return result
