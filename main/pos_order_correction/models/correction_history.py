from collections import defaultdict
from decimal import Decimal

from markupsafe import Markup

from odoo import api, fields, models
from odoo.tools import format_amount, formatLang


class PosOrderCorrection(models.Model):
    _inherit = "pos.order.correction"

    before_details = fields.Html(compute="_compute_history_details", compute_sudo=False)
    after_details = fields.Html(compute="_compute_history_details", compute_sudo=False)

    @api.depends("before_snapshot", "after_snapshot", "state", "currency_id")
    @api.depends_context("lang", "uid", "allowed_company_ids")
    def _compute_history_details(self):
        self.check_access("read")
        self.root_order_id.check_access("read")
        applied = self.filtered(lambda correction: correction.state == "applied")
        labels = applied._history_reference_labels()
        for correction in self:
            correction.before_details = (
                correction._render_history_snapshot(correction.before_snapshot, labels)
                if correction in applied else False
            )
            correction.after_details = (
                correction._render_history_snapshot(correction.after_snapshot, labels)
                if correction in applied else False
            )

    def _history_reference_labels(self):
        """Resolve snapshot references in batches without elevating the reader."""
        references = defaultdict(set)
        for correction in self:
            for snapshot in (correction.before_snapshot, correction.after_snapshot):
                if not snapshot:
                    continue
                for line in snapshot.get("lines", []):
                    references["product.product"].add(line.get("product_id"))
                    references["account.tax"].update(line.get("tax_ids", []))
                    references["product.template.attribute.value"].update(
                        line.get("attribute_value_ids", [])
                    )
                    references["product.template.attribute.value"].update(
                        value.get("custom_product_template_attribute_value_id")
                        for value in line.get("custom_attribute_values", [])
                    )
                references["pos.payment.method"].update(
                    payment.get("payment_method_id") for payment in snapshot.get("payments", [])
                )
        labels = {}
        for model_name, ids in references.items():
            records = self.env[model_name].browse([record_id for record_id in ids if record_id])
            records = records.exists()._filtered_access("read")
            labels[model_name] = {record.id: record.display_name for record in records}
        return labels

    def _render_history_snapshot(self, snapshot, labels):
        self.ensure_one()
        unavailable = self.env._("Not recorded or unavailable")
        empty = self.env._("None")
        if not snapshot:
            return Markup("<p>%s</p>") % unavailable

        def reference(model_name, record_id):
            return labels.get(model_name, {}).get(record_id, unavailable)

        def references(values, key, model_name):
            if key not in values:
                return unavailable
            return ", ".join(reference(model_name, value) for value in values[key]) or empty

        def number(values, key, monetary=False):
            if key not in values or values[key] is None:
                return unavailable
            if monetary:
                return format_amount(self.env, values[key], self.currency_id)
            digits = max(0, -Decimal(str(values[key])).normalize().as_tuple().exponent)
            return formatLang(self.env, values[key], digits=digits)

        def custom_attributes(line):
            if "custom_attribute_values" not in line:
                return unavailable
            return "; ".join(
                "%s: %s" % (
                    reference("product.template.attribute.value", value.get(
                        "custom_product_template_attribute_value_id"
                    )),
                    value.get("custom_value", unavailable),
                )
                for value in line["custom_attribute_values"]
            ) or empty

        def table(title, key, headings, rows):
            heading = Markup("<h5>%s</h5>") % title
            if key not in snapshot:
                return heading + Markup("<p>%s</p>") % unavailable
            if not snapshot[key]:
                return heading + Markup("<p>%s</p>") % empty
            return heading + Markup(
                "<div class='table-responsive'><table class='table table-sm'>"
                "<thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>"
            ) % (
                Markup().join(Markup("<th>%s</th>") % title for title in headings),
                Markup().join(
                    Markup("<tr>%s</tr>") % Markup().join(
                        Markup("<td>%s</td>") % value for value in row
                    ) for row in rows
                ),
            )

        product_rows = [
            (
                reference("product.product", line.get("product_id")),
                number(line, "qty"), number(line, "price_unit"),
                number(line, "discount"), references(line, "tax_ids", "account.tax"),
                (line["lot_names"] or empty) if "lot_names" in line else unavailable,
                references(line, "attribute_value_ids", "product.template.attribute.value"),
                custom_attributes(line),
            ) for line in snapshot.get("lines", [])
        ]
        payment_rows = [
            (reference("pos.payment.method", payment.get("payment_method_id")),
             number(payment, "amount", monetary=True))
            for payment in snapshot.get("payments", [])
        ]
        return table(
            self.env._("Products"), "lines",
            [self.env._("Product"), self.env._("Quantity"),
             "%s (%s)" % (self.env._("Unit Price"), self.currency_id.name),
             self.env._("Discount (%)"), self.env._("Taxes"), self.env._("Lots / Serial Numbers"),
             self.env._("Attributes"), self.env._("Custom Attributes")], product_rows,
        ) + table(
            self.env._("Payments"), "payments",
            [self.env._("Payment Method"), self.env._("Amount")], payment_rows,
        )
