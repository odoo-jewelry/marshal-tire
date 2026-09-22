from odoo import fields, models
from odoo.tools.misc import format_amount


class PurchaseCostRecomputeWizard(models.TransientModel):
    _name = "purchase.cost.recompute.wizard"
    _description = "Purchase Cost Recomputation"

    order_ids = fields.Many2many(
        "purchase.order", string="Purchase Orders", required=True, readonly=True,
    )

    def action_apply(self):
        self.ensure_one()
        self.check_access("write")
        self.order_ids._check_purchase_cost_recompute_access()
        result = self.order_ids._apply_purchase_cost_recompute()
        if result["purchase_lines"]:
            currency = self.env["res.currency"].browse(result["currency_id"])
            message = self.env._(
                "Purchase lines: %(purchase_lines)s; receipts: %(receipts)s; "
                "issues: %(issues)s; returns: %(returns)s; "
                "inventory gains: %(inventory_gains)s; inventory losses: %(inventory_losses)s; "
                "scrap issues: %(scrap_issues)s; "
                "POS lines: %(pos_lines)s. Purchase total difference: %(difference)s.",
                purchase_lines=result["purchase_lines"],
                receipts=result["receipts"],
                issues=result["issues"],
                returns=result["returns"],
                inventory_gains=result["inventory_gains"],
                inventory_losses=result["inventory_losses"],
                scrap_issues=result["scrap_issues"],
                pos_lines=result["pos_lines"],
                difference=format_amount(self.env, result["total_difference"], currency),
            )
        else:
            message = self.env._("No purchase lines required correction.")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Purchase Costs Recomputed"),
                "message": message,
                "type": "success" if result["purchase_lines"] else "info",
                "sticky": True,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
