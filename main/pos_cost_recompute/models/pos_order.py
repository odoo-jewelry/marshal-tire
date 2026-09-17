from odoo import Command, api, models
from odoo.exceptions import UserError


class PosOrder(models.Model):
    _inherit = "pos.order"

    @api.model
    def _load_pos_data_fields(self, config):
        fields_to_load = super()._load_pos_data_fields(config)
        if not fields_to_load:
            # An empty list loads all fields; keep the standard POS exclusion
            # of manual fields and the current user's field access restrictions.
            fields_to_load = [
                name for name in self.fields_get(attributes=()) if not self._fields[name].manual
            ]
        return [name for name in fields_to_load if name != "cost_recompute_revision"]

    @api.model
    def _process_order(self, order, existing_order):
        # Already open or offline POS clients can still send this server-owned
        # counter. Ignore the echoed value without weakening ORM write guards.
        order = {key: value for key, value in order.items() if key != "cost_recompute_revision"}
        return super()._process_order(order, existing_order)

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
