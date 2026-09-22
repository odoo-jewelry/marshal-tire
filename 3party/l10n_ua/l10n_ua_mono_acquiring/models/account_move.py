from odoo import models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _name = 'account.move'
    _inherit = ['account.move', 'l10n_ua.mono.acquiring.mixin']

    def _mono_amount(self):
        self.ensure_one()
        return self.amount_residual

    def _mono_reference(self):
        self.ensure_one()
        return self.name

    def _mono_destination(self):
        self.ensure_one()
        return _("Оплата за рахунком %s") % self.name

    def _mono_basket(self):
        self.ensure_one()
        basket = []
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type in (False, 'product'))
        for line in product_lines:
            product = line.product_id
            code = product.default_code or product.barcode or str(product.id)
            basket.append(self._mono_basket_line(
                name=line.name or product.name,
                qty=line.quantity,
                subtotal=line.price_subtotal,
                unit=line.product_uom_id.name,
                code=code,
                icon=self._mono_product_icon(product),
            ))
        return basket

    def action_create_mono_link(self):
        self.ensure_one()
        if self.move_type != 'out_invoice':
            raise UserError(_(
                "Посилання на оплату можна створити лише для рахунку клієнту."))
        if self.amount_residual <= 0:
            raise UserError(_("Рахунок вже оплачено."))
        return super().action_create_mono_link()
