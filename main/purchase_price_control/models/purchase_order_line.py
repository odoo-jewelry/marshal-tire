from odoo import api, fields, models
from odoo.tools.float_utils import float_compare, float_round


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
    )
    current_purchase_price = fields.Monetary(
        string="Current Reference Purchase Price",
        currency_field="company_currency_id",
        copy=False,
    )
    current_sale_price = fields.Monetary(
        string="Current Sales Price",
        currency_field="company_currency_id",
        copy=False,
    )
    current_markup = fields.Float(string="Current Markup (%)", digits=(16, 2), copy=False)
    current_standard_price = fields.Monetary(
        string="Current Standard Cost",
        currency_field="company_currency_id",
        copy=False,
    )
    price_snapshot_initialized = fields.Boolean(copy=False)
    effective_purchase_price = fields.Monetary(
        string="Purchase Price incl. Taxes",
        currency_field="company_currency_id",
        compute="_compute_calculated_prices",
    )
    planned_sale_price = fields.Monetary(
        string="Planned Sales Price",
        currency_field="company_currency_id",
        compute="_compute_calculated_prices",
    )
    valuation_purchase_price = fields.Monetary(
        string="Calculated Standard Cost",
        currency_field="company_currency_id",
        compute="_compute_calculated_prices",
        help="Purchase cost calculated with Odoo inventory valuation rules.",
    )
    effective_cost_method = fields.Selection(
        selection=[
            ("standard", "Standard Price"),
            ("average", "Average Cost (AVCO)"),
            ("fifo", "First In First Out (FIFO)"),
        ],
        compute="_compute_effective_cost_method",
    )
    price_update_required = fields.Boolean(compute="_compute_price_update_required")

    @api.depends(
        "company_id.purchase_price_rounding",
        "currency_id",
        "current_markup",
        "date_order",
        "discount",
        "display_type",
        "is_downpayment",
        "order_id.partner_id",
        "price_snapshot_initialized",
        "price_unit",
        "product_id",
        "product_uom_id",
        "tax_ids",
    )
    def _compute_calculated_prices(self):
        for line in self:
            line.effective_purchase_price = 0.0
            line.planned_sale_price = 0.0
            line.valuation_purchase_price = 0.0
            if not line._is_price_control_eligible():
                continue
            effective_price = line._get_effective_purchase_price()
            line.effective_purchase_price = effective_price
            line.valuation_purchase_price = line.with_context(
                conversion_date=line.date_order
            )._get_stock_move_price_unit()
            if not line.price_snapshot_initialized:
                continue
            raw_sale_price = effective_price * (1.0 + line.current_markup / 100.0)
            line.planned_sale_price = (
                float_round(
                    raw_sale_price,
                    precision_rounding=line.company_id.purchase_price_rounding,
                    rounding_method="UP",
                )
                if raw_sale_price > 0
                else raw_sale_price
            )

    @api.depends("product_id", "product_id.categ_id.property_cost_method")
    @api.depends_context("company")
    def _compute_effective_cost_method(self):
        for line in self:
            line.effective_cost_method = (
                line.product_id.with_company(line.company_id).cost_method
                if line.product_id
                else False
            )

    @api.depends(
        "company_currency_id.rounding",
        "current_purchase_price",
        "current_sale_price",
        "current_standard_price",
        "effective_cost_method",
        "effective_purchase_price",
        "planned_sale_price",
        "price_snapshot_initialized",
        "valuation_purchase_price",
    )
    def _compute_price_update_required(self):
        for line in self:
            rounding = line.company_currency_id.rounding
            line.price_update_required = bool(
                line._is_price_control_eligible()
                and line.price_snapshot_initialized
                and (
                    float_compare(
                        line.current_purchase_price,
                        line.effective_purchase_price,
                        precision_rounding=rounding,
                    )
                    or float_compare(
                        line.current_sale_price,
                        line.planned_sale_price,
                        precision_rounding=rounding,
                    )
                    or (
                        line.effective_cost_method == "standard"
                        and float_compare(
                            line.current_standard_price,
                            line.valuation_purchase_price,
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
            product.with_company(company).write(values)

    def _get_product_price_values(self):
        self.ensure_one()
        values = {
            "product": self.product_id,
            "company": self.company_id,
            "last_purchase_price": self.effective_purchase_price,
            "lst_price": self.planned_sale_price,
        }
        if self.effective_cost_method == "standard":
            values["standard_price"] = self.valuation_purchase_price
        return values

    def _is_price_control_eligible(self):
        self.ensure_one()
        return bool(self.product_id and not self.display_type and not self.is_downpayment)

    def _get_effective_purchase_price(self):
        self.ensure_one()
        if not self._is_price_control_eligible():
            return 0.0
        company = self.company_id
        purchase_currency = self.currency_id or company.currency_id
        discounted_price = self.price_unit * (1.0 - (self.discount or 0.0) / 100.0)
        tax_result = self.tax_ids.compute_all(
            discounted_price,
            currency=purchase_currency,
            quantity=1.0,
            product=self.product_id,
            partner=self.order_id.partner_id,
        )
        price_per_purchase_uom = tax_result["total_included"]
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
