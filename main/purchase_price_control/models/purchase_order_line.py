from odoo import api, fields, models
from odoo.tools.float_utils import float_round


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    company_currency_id = fields.Many2one(
        related="company_id.currency_id",
        string="Company Currency",
        readonly=True,
    )
    current_purchase_price = fields.Monetary(
        string="Last Purchase Price",
        currency_field="company_currency_id",
        compute="_compute_price_control",
    )
    current_sale_price = fields.Monetary(
        string="Current Sales Price",
        currency_field="company_currency_id",
        compute="_compute_price_control",
    )
    current_markup = fields.Float(
        string="Current Markup (%)",
        compute="_compute_price_control",
        digits=(16, 2),
    )
    effective_purchase_price = fields.Monetary(
        string="Purchase Price incl. Taxes",
        currency_field="company_currency_id",
        compute="_compute_price_control",
    )
    planned_sale_price = fields.Monetary(
        string="Planned Sales Price",
        currency_field="company_currency_id",
        compute="_compute_price_control",
    )
    save_prices = fields.Boolean(string="Save Prices", copy=False)

    @api.depends(
        "company_id.purchase_default_markup",
        "company_id.purchase_price_rounding",
        "currency_id",
        "date_order",
        "discount",
        "display_type",
        "is_downpayment",
        "order_id.partner_id",
        "price_unit",
        "product_id",
        "product_id.last_purchase_price",
        "product_id.lst_price",
        "product_uom_id",
        "tax_ids",
    )
    @api.depends_context("company")
    def _compute_price_control(self):
        for line in self:
            line.current_purchase_price = 0.0
            line.current_sale_price = 0.0
            line.current_markup = 0.0
            line.effective_purchase_price = 0.0
            line.planned_sale_price = 0.0

            if not line._is_price_control_eligible():
                continue

            company = line.company_id
            product = line.product_id.with_company(company)
            current_purchase_price = product.last_purchase_price
            current_sale_price = product.lst_price
            markup = (
                (current_sale_price / current_purchase_price - 1.0) * 100.0
                if current_purchase_price > 0
                else company.purchase_default_markup
            )
            effective_purchase_price = line._get_effective_purchase_price()
            raw_sale_price = effective_purchase_price * (1.0 + markup / 100.0)
            planned_sale_price = (
                float_round(
                    raw_sale_price,
                    precision_rounding=company.purchase_price_rounding,
                    rounding_method="UP",
                )
                if raw_sale_price > 0
                else raw_sale_price
            )

            line.current_purchase_price = current_purchase_price
            line.current_sale_price = current_sale_price
            line.current_markup = markup
            line.effective_purchase_price = effective_purchase_price
            line.planned_sale_price = planned_sale_price

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
        if self.product_uom_id and product_uom:
            price_per_product_uom = self.product_uom_id._compute_price(
                price_per_purchase_uom,
                product_uom,
            )
        else:
            price_per_product_uom = price_per_purchase_uom

        conversion_date = self.date_order or fields.Date.context_today(self)
        return purchase_currency._convert(
            price_per_product_uom,
            company.currency_id,
            company,
            conversion_date,
            round=False,
        )
