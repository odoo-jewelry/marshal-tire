from collections import Counter

from odoo import fields, models
from odoo.exceptions import AccessError


class PosCustomerDebtLinkReview(models.TransientModel):
    _name = "pos.customer.debt.link.review"
    _description = "POS Customer Debt Link Review"

    order_ids = fields.Many2many("pos.order", string="Orders")
    analyzed_count = fields.Integer(readonly=True)
    linked_count = fields.Integer(readonly=True)
    review_count = fields.Integer(readonly=True)

    def action_analyze(self):
        self.ensure_one()
        if not self.env.user.has_group(
            "pos_customer_debt.group_pos_customer_debt_link_manager"
        ):
            raise AccessError(self.env._("You are not allowed to recover debt links."))
        orders = self.order_ids or self.env["pos.order"]._get_debt_candidate_orders()
        orders = orders.filtered(
            lambda order: order.session_id.state == "closed"
            and not order.account_move
            and order.company_id in self.env.companies
        )
        linked = 0
        for order in orders:
            payments = order._get_customer_account_payments().filtered(
                lambda payment: payment.amount > 0.0 and not payment.debt_move_line_ids
            )
            if not payments:
                continue
            accounting_partner = self.env["res.partner"]._find_accounting_partner(
                order.partner_id
            )
            account = accounting_partner.with_company(
                order.company_id
            ).property_account_receivable_id
            candidates = order.session_move_id.line_ids.filtered(
                lambda line: line.parent_state == "posted"
                and not line.pos_debt_payment_id
                and line.partner_id.commercial_partner_id == accounting_partner
                and line.account_id == account
                and line.currency_id == order.currency_id
                and line.amount_currency > 0.0
            )
            payment_amount_counts = Counter(
                order.currency_id.round(payment.amount) for payment in payments
            )
            candidate_amount_counts = Counter(
                order.currency_id.round(line.amount_currency) for line in candidates
            )
            for payment in payments:
                amount = order.currency_id.round(payment.amount)
                matching = candidates.filtered(
                    lambda line: order.currency_id.compare_amounts(
                        line.amount_currency, payment.amount
                    )
                    == 0
                )
                if (
                    payment_amount_counts[amount] == 1
                    and candidate_amount_counts[amount] == 1
                    and len(matching) == 1
                ):
                    matching.pos_debt_payment_id = payment
                    candidates -= matching
                    linked += 1
        orders.invalidate_recordset()
        self.write(
            {
                "analyzed_count": len(orders),
                "linked_count": linked,
                "review_count": len(
                    orders.filtered(lambda order: order.debt_state == "review_required")
                ),
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
