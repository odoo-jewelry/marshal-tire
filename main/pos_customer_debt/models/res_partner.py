from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    pos_debt_count = fields.Integer(compute="_compute_pos_debt_counts", compute_sudo=True)
    pos_debt_review_count = fields.Integer(
        compute="_compute_pos_debt_counts", compute_sudo=True
    )

    @api.depends("child_ids")
    def _compute_pos_debt_counts(self):
        orders = self.env["pos.order"].sudo()._get_debt_candidate_orders()
        by_partner = {}
        for order in orders:
            partner = order.partner_id.commercial_partner_id
            values = by_partner.setdefault(partner.id, {"debt": 0, "review": 0})
            if order.debt_state == "outstanding":
                values["debt"] += 1
            elif order.debt_state == "review_required":
                values["review"] += 1
        for partner in self:
            values = by_partner.get(partner.commercial_partner_id.id, {})
            partner.pos_debt_count = values.get("debt", 0)
            partner.pos_debt_review_count = values.get("review", 0)

    def action_view_pos_customer_debts(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "pos_customer_debt.action_pos_customer_debt"
        )
        action["domain"] = [
            ("partner_id.commercial_partner_id", "=", self.commercial_partner_id.id),
            ("debt_state", "in", ["outstanding", "settled", "review_required"]),
        ]
        return action
