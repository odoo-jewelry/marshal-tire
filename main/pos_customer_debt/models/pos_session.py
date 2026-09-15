from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _get_split_receivable_vals(self, payment, amount, amount_converted):
        values = super()._get_split_receivable_vals(payment, amount, amount_converted)
        if payment.payment_method_id.type == "pay_later":
            values["pos_debt_payment_id"] = payment.id
        return values

    def _reconcile_account_move_lines(self, data):
        result = super()._reconcile_account_move_lines(data)
        self._apply_customer_account_refunds(data.get("pay_later_move_lines"))
        return result

    def _apply_customer_account_refunds(self, pay_later_lines):
        for credit_line in (pay_later_lines or self.env["account.move.line"]).filtered(
            lambda line: line.pos_debt_payment_id.amount < 0.0
            and not line.reconciled
        ):
            refund_order = credit_line.pos_debt_payment_id.pos_order_id
            source_orders = refund_order.lines.refunded_orderline_id.order_id
            if len(source_orders) != 1:
                continue
            source_order = source_orders.filtered(
                lambda order: order.company_id == refund_order.company_id
            )
            if len(source_order) != 1:
                continue
            source_lines = source_order._get_effective_debt_source_lines().filtered(
                lambda line: line.account_id == credit_line.account_id
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
                    pos_customer_debt_reconcile_amount=amount,
                )._reconcile_plan([debit_line | credit_line])
                remaining -= amount
