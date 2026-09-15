from odoo import fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    # Keep the standard technical states while allowing module-specific labels.
    state = fields.Selection(
        selection_add=[
            ("paid", "Paid"),
            ("done", "Posted"),
        ],
    )
