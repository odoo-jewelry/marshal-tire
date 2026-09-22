from odoo import models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'l10n_ua.mono.acquiring.mixin']

    def _mono_amount(self):
        self.ensure_one()
        return self.amount_total

    def _mono_reference(self):
        self.ensure_one()
        return self.name

    def _mono_destination(self):
        self.ensure_one()
        return _("Оплата замовлення %s") % self.name

    def _mono_basket(self):
        self.ensure_one()
        basket = []
        for line in self.order_line.filtered(lambda l: l.product_uom_qty > 0):
            product = line.product_id
            code = product.default_code or product.barcode or str(product.id)
            basket.append(self._mono_basket_line(
                name=product.name,
                qty=line.product_uom_qty,
                subtotal=line.price_subtotal,
                unit=line.product_uom_id.name,
                code=code,
                icon=self._mono_product_icon(product),
            ))
        return basket

    def action_create_mono_link(self):
        self.ensure_one()
        if not self.order_line:
            raise UserError(_("Замовлення не містить позицій."))
        return super().action_create_mono_link()

    def write(self, vals):
        # Зміна складу замовлення знецінює раніше створене посилання.
        if 'order_line' in vals:
            vals.setdefault('mono_payment_link', False)
            vals.setdefault('mono_invoice_id', False)
        return super().write(vals)
