from odoo import models


class PosCustomerDebtAllocation(models.Model):
    _inherit = "pos.customer.debt.allocation"

    def action_apply(self):
        self.order_id.mapped(lambda order: order._get_correction_root())._lock_correction_chain()
        return super().action_apply()
