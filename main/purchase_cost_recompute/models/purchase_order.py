import math

from odoo import Command, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools import float_round

from .product_product import _CONTEXT_KEY, _INTERNAL


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def action_open_cost_recompute(self):
        self._check_purchase_cost_recompute_access()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase_cost_recompute.purchase_cost_recompute_wizard_action"
        )
        action["res_id"] = self.env["purchase.cost.recompute.wizard"].create({
            "order_ids": [Command.set(self.ids)],
        }).id
        return action

    def _check_purchase_cost_recompute_access(self):
        if not (self.env.user.has_group("purchase.group_purchase_manager")
                and self.env.user.has_group("stock.group_stock_manager")):
            raise AccessError(self.env._(
                "Purchase and Inventory manager permissions are both required."
            ))
        if not self or self.exists() != self:
            raise UserError(self.env._("Select existing purchase orders to recompute."))
        self.check_access("read")
        self.check_access("write")
        companies = self.company_id
        if len(companies) != 1 or companies not in self.env.companies:
            raise AccessError(self.env._("Select purchases from one allowed company."))

    def _lock_purchase_cost_records(self, records):
        if records:
            records.check_access("read")
            records.sorted("id").lock_for_update()
            records.invalidate_recordset()
        return records

    def _purchase_cost_search(self, model, domain, order="id"):
        records = self.env[model].with_context(active_test=False).search(domain, order=order)
        # Only compare existence counts under sudo, never expose hidden values.
        if self.env[model].sudo().with_context(active_test=False).search_count(domain) != len(records):
            raise AccessError(self.env._("Access to the complete correction history is required."))
        return records

    def _lock_purchase_cost_parents(self):
        company = self.company_id
        self._lock_purchase_cost_records(company | company.parent_ids)
        # A previously drafted valuation closing can be posted without changing
        # a purchase product. Lock the standard closing references and their
        # moves, including drafts. Only identifiers are read with elevated rights;
        # the standard period check below reads their closing boundary.
        closing_refs = self.env["ir.config_parameter"].sudo().search([
            ("key", "=", f"{company.id}.stock_valuation_closing_ids"),
        ])
        self._lock_purchase_cost_records(closing_refs)
        closing_ids = [int(value) for reference in closing_refs for value in reference.value.split(",") if value]
        self._lock_purchase_cost_records(self.env["account.move"].sudo().browse(closing_ids).exists())
        lines = self._purchase_cost_search("purchase.order.line", [("order_id", "in", self.ids)])
        products = lines.product_id
        templates = products.product_tmpl_id
        locked_templates, locked_products = templates, products
        if "merged_source_ids" in templates._fields:
            # Archived source identities and versions prove that no history was
            # left behind, including children invisible to an older snapshot.
            sources = templates.sudo().with_context(active_test=False).merged_source_ids
            locked_templates = (templates | sources).sudo().with_context(active_test=False)
            locked_products = (products | sources.product_variant_ids).sudo().with_context(active_test=False)
        # The existing product revision also covers previously invisible child
        # inserts. A stale repeatable-read snapshot must fail here, before planning.
        for records in (
            locked_templates, locked_products, products.categ_id,
            products.uom_id | lines.product_uom_id, self, lines,
            lines.tax_ids, lines.tax_ids.invoice_repartition_line_ids
            | lines.tax_ids.refund_repartition_line_ids,
            company.currency_id | self.currency_id,
            # precision_get() is normally available without configuration ACLs.
            # Elevate only this technical setting to lock the same public value.
            self.env["decimal.precision"].sudo().search([
                ("name", "in", ["Product Price", "Product Unit"]),
            ]),
        ):
            self._lock_purchase_cost_records(records)
        return lines

    def _prepare_purchase_cost_plan(self):
        lines = self._lock_purchase_cost_parents()
        company = self.company_id
        if any(order.state != "purchase" or order.locked for order in self):
            raise UserError(self.env._("Only confirmed, unlocked purchase orders can be corrected."))
        if self.currency_id != company.currency_id:
            raise UserError(self.env._("Purchases must use the company currency."))
        if self.env["decimal.precision"].precision_get("Product Price") != 2:
            raise UserError(self.env._("Product Price precision must already be set to two decimal places."))
        lines = lines.filtered(lambda line: not line.display_type)
        if not lines:
            raise UserError(self.env._("The selected purchases have no product lines."))
        lines.check_access("write")
        changes = []
        for line in lines:
            if line.is_downpayment or line.product_id.type != "consu":
                raise UserError(self.env._(
                    "%(order)s, %(product)s: purchase lines must contain goods and must not be advance payments.",
                    order=line.order_id.display_name, product=line.product_id.display_name,
                ))
            if line.product_uom_id != line.product_id.uom_id:
                raise UserError(self.env._(
                    "%(order)s, %(product)s: the purchase unit must match the product base unit.",
                    order=line.order_id.display_name, product=line.product_id.display_name,
                ))
            if (not math.isfinite(line.product_qty) or line.product_qty <= 0
                    or not math.isfinite(line.price_unit) or line.price_unit <= 0
                    or not math.isfinite(line.discount) or not 0 <= line.discount < 100):
                raise UserError(self.env._(
                    "Purchase quantities and prices must be positive and finite; discounts must be between 0 and 100 percent."
                ))
            if line.product_uom_id.compare(line.qty_received, line.product_qty):
                raise UserError(self.env._(
                    "%(order)s, %(product)s: the purchase line must be fully received.",
                    order=line.order_id.display_name, product=line.product_id.display_name,
                ))
            taxes = line.tax_ids
            if any(tax.company_id != company or tax.amount_type != "percent"
                   or tax.price_include or tax.has_negative_factor
                   or not math.isfinite(tax.amount) or tax.amount < 0
                   for tax in taxes):
                raise UserError(self.env._(
                    "Only nonnegative percentage taxes excluded from the price are supported."
                ))
            if not taxes.filtered(lambda tax: tax.amount > 0):
                continue
            total = taxes.with_context(round_base=False).compute_all(
                line.price_unit, currency=company.currency_id, quantity=1,
                product=line.product_id, partner=line.order_id.partner_id,
                rounding_method="round_globally",
            )["total_included"]
            price = float_round(total, precision_digits=2, rounding_method="HALF-UP")
            if not math.isfinite(price) or price <= 0:
                raise UserError(self.env._("The rounded tax-inclusive price must be positive and finite."))
            changes.append((line, price))
        if not changes:
            return {"changes": [], "company": company}
        for order in self:
            self._check_purchase_history_period(order.date_order)
            if order.date_approve:
                self._check_purchase_history_period(order.date_approve)
        # Draft bills are also financial dependencies. Reading only existence
        # allows a purchase manager to receive a refusal without accounting ACLs.
        if self.env["account.move.line"].sudo().search_count([
            ("purchase_line_id", "in", lines.ids),
            ("move_id.state", "!=", "cancel"),
        ]):
            raise UserError(self.env._("A non-cancelled vendor bill prevents purchase correction."))
        plan = self._prepare_purchase_history_plan(changes, fields.Datetime.now())
        plan.update(changes=changes, company=company)
        return plan

    def _apply_purchase_cost_recompute(self):
        self._check_purchase_cost_recompute_access()
        company = self.company_id
        # Discard RPC-supplied valuation, date and tax overrides. The identity
        # token cannot be forged through JSON and survives standard sudo calls.
        orders = self.with_context({
            "lang": self.env.lang, "tz": self.env.user.tz,
            "allowed_company_ids": company.ids, _CONTEXT_KEY: _INTERNAL,
        }).with_company(company)
        with self.env.cr.savepoint():
            plan = orders._prepare_purchase_cost_plan()
            result = dict.fromkeys((
                "purchase_lines", "receipts", "issues", "returns", "pos_lines",
                "inventory_gains", "inventory_losses", "scrap_issues",
            ), 0)
            result.update(total_difference=0.0, currency_id=company.currency_id.id)
            if not plan["changes"]:
                return result
            previous_total = sum(orders.mapped("amount_total"))
            for line, price in plan["changes"]:
                # price_unit triggers standard purchase_stock receipt valuation,
                # even when the rounded number itself happens not to change.
                line.write({"price_unit": price, "tax_ids": [Command.clear()]})
                if line.price_unit != price or line.tax_ids:
                    raise UserError(orders.env._("The purchase line did not retain its corrected price and empty taxes."))
            orders._recompute_purchase_history(plan)
            orders._recompute_purchase_pos_costs(plan["pos_plan"])
            plan["products"]._update_standard_price()
            result.update(
                purchase_lines=len(plan["changes"]), receipts=len(plan["receipts"]),
                issues=len(plan["issues"]), returns=len(plan["returns"]),
                inventory_gains=len(plan["inventory_gains"]),
                inventory_losses=len(plan["inventory_losses"]),
                scrap_issues=len(plan["scrap_issues"]),
                pos_lines=sum(len(item["lines"]) for item in plan["pos_plan"]),
                total_difference=company.currency_id.round(
                    sum(orders.mapped("amount_total")) - previous_total
                ),
            )
            return result
