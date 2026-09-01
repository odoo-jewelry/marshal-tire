from odoo import _, models
from odoo.exceptions import UserError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def _check_line_import_allowed(self):
        self.ensure_one()
        self.check_access("write")
        if self.state != "draft" or self.locked:
            raise UserError(_("Purchase lines can only be imported into an unlocked draft order."))
        if not self.partner_id:
            raise UserError(_("Select a vendor before importing purchase lines."))
        if self.env["purchase.order.line"].search_count(
            [("order_id", "=", self.id)], limit=1
        ):
            raise UserError(_("Purchase lines can only be imported into an empty order."))

    def action_open_line_import(self):
        self.ensure_one()
        self._check_line_import_allowed()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase_import.purchase_order_line_import_wizard_action"
        )
        action["context"] = {
            **self.env.context,
            "default_order_id": self.id,
        }
        return action
