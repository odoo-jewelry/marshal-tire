from odoo import fields, models


class ReportPosOrder(models.Model):
    _inherit = "report.pos.order"

    total_cost = fields.Float(string="Cost", readonly=True, aggregator="sum")

    def _select(self):
        return super()._select() + """
            , COALESCE(l.total_cost, 0)
              / COALESCE(NULLIF(s.currency_rate, 0), 1.0) AS total_cost
        """
