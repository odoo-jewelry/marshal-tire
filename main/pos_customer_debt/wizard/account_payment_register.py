from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    pos_debt_order_ids = fields.Many2many(
        "pos.order",
        string="POS Customer Debts",
        readonly=True,
    )
    pos_debt_allocation_line_ids = fields.One2many(
        "pos.customer.debt.payment.register.line",
        "wizard_id",
        string="Debt Distribution",
    )
    pos_debt_created_payment_id = fields.Many2one(
        "account.payment",
        readonly=True,
        string="Created Debt Payment",
    )

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        order_ids = self.env.context.get("pos_customer_debt_order_ids", [])
        orders = self.env["pos.order"].browse(order_ids).exists()
        if orders:
            orders._check_debt_orders_compatible()
            values["pos_debt_order_ids"] = [(6, 0, orders.ids)]
            values["pos_debt_allocation_line_ids"] = [
                (0, 0, {"order_id": order.id, "amount": order.debt_residual_amount})
                for order in orders
            ]
        return values

    def _reconcile_payments(self, to_process, edit_mode=False):
        if not self.pos_debt_order_ids:
            return super()._reconcile_payments(to_process, edit_mode=edit_mode)
        payment = self.env["account.payment"].union(
            *(values["payment"] for values in to_process)
        )
        if len(payment) != 1:
            raise UserError(self.env._("Debt distribution requires exactly one payment."))
        allocations = self.env["pos.customer.debt.allocation"].create(
            [
                {
                    "payment_id": payment.id,
                    "order_id": line.order_id.id,
                    "amount": line.amount,
                }
                for line in self.pos_debt_allocation_line_ids
            ]
        )
        allocations.action_apply()

    def _create_payments(self):
        self.ensure_one()
        if not self.pos_debt_order_ids:
            return super()._create_payments()
        if self.try_lock_for_update() != self:
            raise UserError(
                self.env._(
                    "Debt payment registration is already being processed. Refresh and try again."
                )
            )
        self.invalidate_recordset(["pos_debt_created_payment_id"])
        if self.pos_debt_created_payment_id.exists():
            return self.pos_debt_created_payment_id
        payments = super()._create_payments()
        if len(payments) != 1:
            raise UserError(self.env._("Debt distribution requires exactly one payment."))
        self.pos_debt_created_payment_id = payments
        return payments


class PosCustomerDebtPaymentRegisterLine(models.TransientModel):
    _name = "pos.customer.debt.payment.register.line"
    _description = "POS Customer Debt Payment Distribution"

    wizard_id = fields.Many2one(
        "account.payment.register",
        required=True,
        ondelete="cascade",
    )
    order_id = fields.Many2one("pos.order", required=True, readonly=True)
    currency_id = fields.Many2one(related="order_id.currency_id")
    amount = fields.Monetary(required=True, currency_field="currency_id")
