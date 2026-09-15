from odoo import api, fields, models
from odoo.fields import Domain


class PosOrderTicketData(models.Model):
    _inherit = "pos.order"

    correction_has_applied = fields.Boolean(compute="_compute_correction_ticket_data")
    correction_current_tax = fields.Monetary(compute="_compute_correction_ticket_data")

    @api.depends(
        "correction_ids.state", "correction_ids.applied_order_id.amount_tax",
        "amount_tax", "correction_root_id.correction_ids.state",
    )
    def _compute_correction_ticket_data(self):
        for order in self:
            chain = order._get_correction_chain()
            order.correction_has_applied = len(chain) > 1
            order.correction_current_tax = sum(chain.mapped("amount_tax"))

    def read_pos_data(self, data, config):
        # Load real line owners as well as the read-only current relation.
        # Never substitute the original lines or their inverse order_id.
        orders = self | self.mapped(lambda order: order._get_correction_chain())
        return super(PosOrderTicketData, orders).read_pos_data(data, config)

    @api.model
    def search_paid_order_ids(self, config_id, domain, limit, offset):
        result = super().search_paid_order_ids(
            config_id, Domain(domain) & Domain("is_correction_order", "=", False), limit, offset
        )
        refreshed = []
        for order_id, last_modified in result["ordersInfo"]:
            order = self.browse(order_id)
            if order.correction_has_applied:
                chain = order._get_correction_chain()
                dates = (
                    chain.mapped("write_date") + chain.session_id.mapped("write_date")
                    + order.correction_ids.mapped("write_date")
                    + chain.lines.refund_orderline_ids.mapped("write_date")
                )
                last_modified = max([last_modified] + [date for date in dates if date])
            refreshed.append((order_id, last_modified))
        result["ordersInfo"] = refreshed
        return result
