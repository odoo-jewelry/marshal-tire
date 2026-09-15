from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import format_amount


class PosOrder(models.Model):
    _inherit = "pos.order"

    correction_count = fields.Integer(compute="_compute_correction_projection")
    correction_current_line_ids = fields.Many2many(
        "pos.order.line", compute="_compute_correction_projection", string="Current Products"
    )
    correction_current_payments = fields.Html(
        compute="_compute_correction_projection", string="Current Payments"
    )
    correction_current_total = fields.Monetary(
        compute="_compute_correction_projection", string="Current Total"
    )
    correction_stock_pending = fields.Boolean(
        compute="_compute_correction_projection", string="Stock Processing Pending"
    )

    @api.depends(
        "lines", "lines.qty", "lines.price_subtotal_incl", "amount_total",
        "payment_ids.amount", "payment_ids.payment_method_id",
        "correction_ids.state", "correction_ids.applied_order_id",
        "correction_ids.applied_order_id.payment_ids.amount",
        "correction_ids.applied_order_id.amount_total",
        "correction_ids.applied_order_id.lines",
        "correction_ids.applied_order_id.picking_ids.state",
        "correction_ids.applied_order_id.session_id.state",
        "picking_ids.state", "session_id.state", "correction_root_id",
        "correction_root_id.correction_ids.state",
        "correction_root_id.correction_ids.applied_order_id.payment_ids.amount",
        "correction_root_id.correction_ids.applied_order_id.session_id.state",
    )
    def _compute_correction_projection(self):
        for order in self:
            root = order._get_correction_root()
            chain = root._get_correction_chain()
            order.correction_count = len(root.correction_ids)
            order.correction_current_line_ids = root._get_effective_correction_lines()
            order.correction_current_total = sum(chain.mapped("amount_total"))
            amounts = {}
            for payment in chain.payment_ids:
                method = payment.payment_method_id
                amounts[method] = amounts.get(method, 0.0) + payment.amount
            rows = [
                Markup("<tr><td>%s</td><td class='text-end'>%s</td></tr>") % (
                    method.display_name, format_amount(self.env, amount, root.currency_id)
                )
                for method, amount in sorted(amounts.items(), key=lambda item: item[0].id)
                if not root.currency_id.is_zero(amount)
            ]
            order.correction_current_payments = (
                Markup("<table class='table table-sm'><tbody>%s</tbody></table>")
                % Markup().join(rows)
            )
            order.correction_stock_pending = bool(root.correction_ids.filtered(
                lambda correction: correction.state == "applied"
            )) and (
                any(picking.state not in ("done", "cancel") for picking in chain.picking_ids)
                or any(
                    item.session_id.update_stock_at_closing
                    and item.session_id.state != "closed"
                    and item.lines.filtered(lambda line: line.product_id.type == "consu")
                    for item in chain
                )
            )

    def action_open_correction_history(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Correction History"),
            "res_model": "pos.order.correction",
            "view_mode": "list,form",
            "domain": [("root_order_id", "=", self._get_correction_root().id)],
        }
