from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_invoice(self):
        """Пробросити договір із замовлення у рахунок."""
        vals = super()._prepare_invoice()
        if self.agreement_id:
            vals['agreement_id'] = self.agreement_id.id
        return vals
