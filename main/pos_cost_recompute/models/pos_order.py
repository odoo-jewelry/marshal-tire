from odoo import Command, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    def action_prepare_cost_recompute(self):
        self.env["pos.cost.recompute"]._check_manager()
        self.check_access("read")
        if not self or len(self.company_id) != 1:
            raise UserError(self.env._("Select orders from exactly one company."))
        operation = self.env["pos.cost.recompute"].create({
            "company_id": self.company_id.id,
            "selection_type": "orders",
            "order_ids": [Command.set(self.ids)],
        })
        return operation._get_action()

    def action_view_cost_recomputations(self):
        self.env["pos.cost.recompute"]._check_manager()
        self.check_access("read")
        action = self.env["ir.actions.actions"]._for_xml_id(
            "pos_cost_recompute.pos_cost_recompute_action"
        )
        action["domain"] = [("line_ids.pos_line_id.order_id", "in", self.ids)]
        return action
