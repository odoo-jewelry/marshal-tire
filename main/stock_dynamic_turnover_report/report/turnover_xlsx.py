"""Export the dynamic stock report through the shared XLSX route."""

from io import BytesIO
import json

import xlsxwriter

from odoo import api, models
from odoo.exceptions import AccessError, UserError

from .stock_dynamic_turnover import OPERATIONS


OPERATION_NAMES = {
    "historical_writeoff": "Historical write-off",
    "scrap": "Scrap",
    "internal_transfer": "Internal transfer",
    "customer_return": "Customer return",
    "supplier_return": "Supplier return",
    "inventory_gain": "Inventory gain",
    "inventory_loss": "Inventory loss",
    "pos_sale": "POS sale",
    "sale_delivery": "Sales delivery",
    "supplier_receipt": "Supplier receipt",
    "other": "Other",
}


class StockDynamicTurnoverXlsx(models.AbstractModel):
    _inherit = "stock.dynamic.turnover.report"

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        if report_action != "stock_dynamic_turnover_report.action_stock_dynamic_turnover":
            raise AccessError(self.env._("Invalid stock report action."))
        try:
            payload = json.loads(data)
        except (TypeError, ValueError):
            raise UserError(self.env._("Invalid stock report export."))
        if not isinstance(payload, dict) or set(payload) != {"options", "revision"}:
            raise UserError(self.env._("Invalid stock report export."))
        options = payload["options"]
        revision = payload["revision"]
        if not isinstance(revision, str) or len(revision) != 64:
            raise UserError(self.env._("Refresh the report before export."))
        params, rows, diagnostics, _canonical, current = self._calculate(options)
        if current != revision:
            raise UserError(self.env._("The report sources changed. Refresh the report."))
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Stock Turnover")
        header = workbook.add_format({"bold": True, "bg_color": "#DDE9F3"})
        number = workbook.add_format({"num_format": "#,##0.00;[Red]-#,##0.00"})
        sheet.freeze_panes(3, 2)
        sheet.set_column(0, 0, 46)
        sheet.set_column(1, 1, 12)
        sheet.set_column(2, 30, 18)
        sheet.write_string(0, 0, self.env._("Stock Turnover"))
        sheet.write_string(1, 0, "%s — %s" % (params["date_from"], params["date_to"]))
        sheet.write_string(1, 3, self.env._("Currency: %s") % params["company"].currency_id.name)
        labels = [
            self.env._("Dimension"), self.env._("Unit"),
            self.env._("Opening quantity"), self.env._("Opening value"),
            self.env._("Incoming quantity"), self.env._("Incoming value"),
            self.env._("Outgoing quantity"), self.env._("Outgoing value"),
            self.env._("Closing quantity"), self.env._("Closing value"),
            self.env._("Valuation difference"),
        ]
        if params["columns"] == "operations":
            for operation in OPERATIONS:
                operation_label = self.env._(OPERATION_NAMES[operation])
                labels.extend((
                    "%s %s" % (operation_label, self.env._("quantity")),
                    "%s %s" % (operation_label, self.env._("value")),
                ))
        for column, label in enumerate(labels):
            sheet.write_string(2, column, label, header)
        line_number = 3
        for row in rows:
            measures = row["measures"]
            unit_ids = set()
            for section in ("opening", "incoming", "outgoing", "closing"):
                unit_ids.update(int(unit_id) for unit_id in measures[section + "_qty"])
            if not unit_ids:
                unit_ids = {0}
            for index, unit_id in enumerate(sorted(unit_ids)):
                sheet.write_string(line_number, 0, "  " * row["level"] + row["label"])
                if unit_id:
                    unit = self.env["uom.uom"].browse(unit_id)
                    sheet.write_string(line_number, 1, unit.name)
                for column, section in ((2, "opening"), (4, "incoming"), (6, "outgoing"), (8, "closing")):
                    quantity = measures[section + "_qty"].get(unit_id, measures[section + "_qty"].get(str(unit_id), 0.0))
                    sheet.write_number(line_number, column, quantity, number)
                    if index == 0 and measures[section + "_value"] is not None:
                        sheet.write_number(line_number, column + 1, measures[section + "_value"], number)
                if index == 0 and measures["valuation_delta"] is not None:
                    sheet.write_number(line_number, 10, measures["valuation_delta"], number)
                if params["columns"] == "operations":
                    for offset, operation in enumerate(OPERATIONS):
                        value = row["operations"].get(operation, {})
                        quantity = value.get("quantity", {}).get(unit_id, value.get("quantity", {}).get(str(unit_id), 0.0))
                        sheet.write_number(line_number, 11 + offset * 2, quantity, number)
                        if index == 0 and value.get("value") is not None:
                            sheet.write_number(line_number, 12 + offset * 2, value["value"], number)
                line_number += 1
            for reason in row["diagnostics"]:
                sheet.write_string(line_number, 0, self.env._("Diagnostic: %s") % reason)
                line_number += 1
        for reason in diagnostics:
            sheet.write_string(line_number, 0, self.env._("Diagnostic: %s") % str(reason))
            line_number += 1
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
