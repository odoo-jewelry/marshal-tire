from odoo import models
from odoo.exceptions import UserError


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_reconciliation_plan(
        self, plan, amls_values_map, shadowed_aml_values=None
    ):
        amount = self.env.context.get("pos_customer_debt_reconcile_amount")
        if amount:
            lines = plan.get("amls", self.env["account.move.line"])
            if len(lines) != 2 or len(lines.currency_id) != 1:
                raise UserError(
                    self.env._(
                        "A debt allocation must reconcile exactly two lines in one currency."
                    )
                )
            currency = lines.currency_id
            for line in lines:
                values = dict(amls_values_map[line])
                residual_currency = values["amount_residual_currency"]
                residual = values["amount_residual"]
                capped_currency = min(abs(residual_currency), amount)
                if currency.is_zero(capped_currency):
                    raise UserError(
                        self.env._("There is no residual amount left to allocate.")
                    )
                ratio = abs(residual / residual_currency) if residual_currency else 0.0
                values["amount_residual_currency"] = (
                    capped_currency if residual_currency > 0.0 else -capped_currency
                )
                capped_residual = line.company_currency_id.round(capped_currency * ratio)
                values["amount_residual"] = (
                    capped_residual if residual > 0.0 else -capped_residual
                )
                amls_values_map[line] = values
        return super()._prepare_reconciliation_plan(
            plan, amls_values_map, shadowed_aml_values=shadowed_aml_values
        )

    def reconcile(self):
        order_id = self.env.context.get("pos_customer_debt_invoice_order_id")
        if order_id:
            order = self.env["pos.order"].browse(order_id).exists()
            if order:
                allowed_session_lines = order._get_session_debt_source_lines()
                self = self.filtered(
                    lambda line: line.move_id != order.session_move_id
                    or line in allowed_session_lines
                )
        return super(AccountMoveLine, self).reconcile()
