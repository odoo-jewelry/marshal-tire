from odoo import models


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_confirm(self):
        orders_to_confirm = self.filtered(lambda order: order.state in ("draft", "sent"))
        lines_to_save = orders_to_confirm.order_line.filtered(
            lambda line: line.save_prices and line._is_price_control_eligible()
        ).sorted(key=lambda line: (line.order_id.id, line.sequence, line.id))
        price_values = [
            (
                line.product_id,
                line.company_id,
                line.effective_purchase_price,
                line.planned_sale_price,
            )
            for line in lines_to_save
        ]

        result = super().button_confirm()

        for product, company, purchase_price, sale_price in price_values:
            product.with_company(company).write({
                "last_purchase_price": purchase_price,
                "lst_price": sale_price,
            })
        return result
