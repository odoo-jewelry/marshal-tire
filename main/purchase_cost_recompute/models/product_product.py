from odoo import models


_INTERNAL = object()
_CONTEXT_KEY = "purchase_cost_recompute_internal"


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_last_in(self, date=None):
        if self.env.context.get(_CONTEXT_KEY) is not _INTERNAL:
            return super()._get_last_in(date=date)

        self.ensure_one()
        # Standard cost refresh can call this method with sudo(). Keep its
        # receipt source inside the company already authorized by the action.
        domain = [
            ("company_id", "=", self.env.company.id),
            ("product_id", "=", self.id),
            ("state", "=", "done"),
            ("is_in", "=", True),
        ]
        if date:
            domain.append(("date", "<=", date))
        return self.env["stock.move"].search(
            domain, order="date desc, id desc", limit=1,
        )
