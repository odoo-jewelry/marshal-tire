from odoo import api, fields, models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    has_price_control_lines = fields.Boolean(compute="_compute_price_control_flags")
    has_price_updates = fields.Boolean(compute="_compute_price_control_flags")

    @api.depends(
        "order_line.display_type",
        "order_line.is_downpayment",
        "order_line.price_update_required",
        "order_line.product_id",
    )
    def _compute_price_control_flags(self):
        for order in self:
            eligible_lines = order.order_line.filtered(
                lambda line: line._is_price_control_eligible()
            )
            order.has_price_control_lines = bool(eligible_lines)
            order.has_price_updates = any(eligible_lines.mapped("price_update_required"))

    def action_fill_current_prices(self):
        self._refresh_price_snapshots(reset_manual_price=True)
        return True

    def action_update_all_prices(self):
        candidates = self.order_line.filtered(lambda line: line.price_update_required)
        payload = candidates._get_price_update_payload()
        if not payload:
            return True
        candidates._apply_price_update_payload(payload)
        self._refresh_price_snapshots()
        return True

    def _refresh_price_snapshots(self, reset_manual_price=False):
        for line in self.order_line.filtered(
            lambda candidate: candidate._is_price_control_eligible()
        ):
            product = line.product_id.with_company(line.company_id)
            standard_price = product.standard_price
            sale_price = product.lst_price
            markup = (
                (sale_price / standard_price - 1.0) * 100.0
                if standard_price > 0
                else line.company_id.purchase_default_markup
            )
            values = {
                "current_sale_price": sale_price,
                "current_markup": markup,
                "current_standard_price": standard_price,
                "price_snapshot_initialized": True,
            }
            if reset_manual_price:
                values.update({
                    "planned_sale_price_manually_set": False,
                    "planned_sale_price_override": 0.0,
                })
            line.write(values)
