from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_round


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
    )
    current_standard_price = fields.Monetary(
        string="Current Cost",
        currency_field="company_currency_id",
        copy=False,
    )
    current_markup = fields.Float(string="Markup", digits=(16, 2), copy=False)
    current_sale_price = fields.Monetary(
        string="Current Sale",
        currency_field="company_currency_id",
        copy=False,
    )
    price_snapshot_initialized = fields.Boolean(copy=False)
    planned_sale_price = fields.Monetary(
        string="New Sale",
        currency_field="company_currency_id",
        compute="_compute_planned_sale_price",
        inverse="_inverse_planned_sale_price",
        readonly=False,
    )
    planned_sale_price_override = fields.Monetary(
        currency_field="company_currency_id",
        copy=False,
    )
    planned_sale_price_manually_set = fields.Boolean(copy=False)
    price_update_required = fields.Boolean(compute="_compute_price_update_required")

    @api.depends(
        "company_id.purchase_price_rounding",
        "currency_id",
        "current_markup",
        "date_order",
        "discount",
        "display_type",
        "is_downpayment",
        "price_snapshot_initialized",
        "planned_sale_price_manually_set",
        "planned_sale_price_override",
        "price_unit",
        "product_id",
        "product_uom_id",
    )
    def _compute_planned_sale_price(self):
        for line in self:
            line.planned_sale_price = 0.0
            if not line._is_price_control_eligible():
                continue
            if not line.price_snapshot_initialized:
                continue
            if line.planned_sale_price_manually_set:
                line.planned_sale_price = line.planned_sale_price_override
                continue
            raw_sale_price = line._get_purchase_price_basis() * (
                1.0 + line.current_markup / 100.0
            )
            line.planned_sale_price = (
                float_round(
                    raw_sale_price,
                    precision_rounding=line.company_id.purchase_price_rounding,
                    rounding_method="UP",
                )
                if raw_sale_price > 0
                else raw_sale_price
            )

    def _inverse_planned_sale_price(self):
        invalid_lines = self.filtered(
            lambda line: not line._is_price_control_eligible()
            or not line.price_snapshot_initialized
        )
        if invalid_lines:
            raise ValidationError(
                self.env._(
                    "New Sale can only be entered for an initialized "
                    "product line."
                )
            )
        for line in self:
            line.planned_sale_price_override = line.planned_sale_price
            line.planned_sale_price_manually_set = True

    @api.depends(
        "company_currency_id.rounding",
        "current_sale_price",
        "current_standard_price",
        "currency_id",
        "date_order",
        "discount",
        "display_type",
        "is_downpayment",
        "planned_sale_price",
        "price_snapshot_initialized",
        "price_unit",
        "product_id",
        "product_id.categ_id.property_cost_method",
        "product_uom_id",
    )
    def _compute_price_update_required(self):
        for line in self:
            rounding = line.company_currency_id.rounding
            cost_method = (
                line.product_id.with_company(line.company_id).cost_method
                if line.product_id
                else False
            )
            line.price_update_required = bool(
                line._is_price_control_eligible()
                and line.price_snapshot_initialized
                and (
                    float_compare(
                        line.current_sale_price,
                        line.planned_sale_price,
                        precision_rounding=rounding,
                    )
                    or (
                        cost_method == "standard"
                        and float_compare(
                            line.current_standard_price,
                            line._get_purchase_price_basis(),
                            precision_rounding=rounding,
                        )
                    )
                )
            )

    def action_update_product_prices(self):
        candidates = self.filtered(lambda line: line.price_update_required)
        payload = candidates._get_price_update_payload()
        candidates._apply_price_update_payload(payload)
        candidates.order_id._refresh_price_snapshots()
        return True

    def _get_price_update_payload(self):
        return [
            line._get_product_price_values()
            for line in self.sorted(
                key=lambda line: (line.order_id.id, line.sequence, line.id)
            )
            if line._is_price_control_eligible()
            and line.price_snapshot_initialized
            and line.price_update_required
        ]

    def _apply_price_update_payload(self, payload):
        final_cost_indexes = {
            (values["company"].id, values["product"].id): index
            for index, values in enumerate(payload)
            if "standard_price" in values
        }
        for index, payload_values in enumerate(payload):
            values = payload_values.copy()
            product = values.pop("product")
            company = values.pop("company")
            if final_cost_indexes.get((company.id, product.id)) != index:
                values.pop("standard_price", None)
            product = product.with_company(company)
            self._check_price_control_product_write_access(product, values)
            changed_values = {
                field_name: value
                for field_name, value in values.items()
                if not self._price_control_values_match(
                    {field_name: value}, record=product
                )
            }
            if changed_values:
                product.write(changed_values)

    def _get_product_price_values(self):
        self.ensure_one()
        values = {
            "product": self.product_id,
            "company": self.company_id,
            "lst_price": self.planned_sale_price,
        }
        if self.product_id.with_company(self.company_id).cost_method == "standard":
            values["standard_price"] = self._get_purchase_price_basis()
        return values

    def _is_price_control_eligible(self):
        self.ensure_one()
        return bool(self.product_id and not self.display_type and not self.is_downpayment)

    def _get_purchase_price_basis(self):
        self.ensure_one()
        if not self._is_price_control_eligible():
            return 0.0
        company = self.company_id
        purchase_currency = self.currency_id or company.currency_id
        price_per_purchase_uom = self.price_unit * (
            1.0 - (self.discount or 0.0) / 100.0
        )
        product_uom = self.product_id.uom_id
        price_per_product_uom = (
            self.product_uom_id._compute_price(price_per_purchase_uom, product_uom)
            if self.product_uom_id and product_uom
            else price_per_purchase_uom
        )
        conversion_date = self.date_order or fields.Date.context_today(self)
        return purchase_currency._convert(
            price_per_product_uom,
            company.currency_id,
            company,
            conversion_date,
            round=False,
        )

    def _check_price_control_write_access(self, field_names):
        self.check_access("write")
        for field_name in field_names:
            self._check_field_access(self._fields[field_name], "write")

    def _check_price_control_product_write_access(self, product, values):
        product.check_access("write")
        for field_name in values:
            product._check_field_access(product._fields[field_name], "write")
        if "lst_price" in values:
            product._check_field_access(product._fields["list_price"], "write")
            templates = product.product_tmpl_id
            templates.check_access("write")
            templates._check_field_access(templates._fields["list_price"], "write")

    def _price_control_values_match(self, values, record=None):
        record = record or self
        record.ensure_one()
        for field_name, value in values.items():
            field = record._fields[field_name]
            if field.convert_to_cache(
                record[field_name], record
            ) != field.convert_to_cache(value, record):
                return False
        return True
