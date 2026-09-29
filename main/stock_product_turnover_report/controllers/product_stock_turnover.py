"""Authenticated XLSX download for the product stock turnover statement."""

import json

from werkzeug.exceptions import BadRequest

from odoo import http
from odoo.http import content_disposition, request


class ProductStockTurnoverController(http.Controller):

    @http.route(
        "/stock_product_turnover_report/export",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=True,
    )
    def export_xlsx(self, options=None, fingerprint=None, **kwargs):
        if not isinstance(options, str) or len(options) > 100_000 or not isinstance(fingerprint, str):
            raise BadRequest()
        try:
            filters = json.loads(options)
        except (TypeError, ValueError):
            raise BadRequest() from None
        if not isinstance(filters, dict):
            raise BadRequest()
        payload = request.env["stock.product.turnover.report"].get_xlsx(filters, fingerprint)
        return request.make_response(
            payload,
            headers=[
                ("Content-Type", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                ("Content-Disposition", content_disposition("product_stock_turnover.xlsx")),
                ("Content-Length", str(len(payload))),
            ],
        )
