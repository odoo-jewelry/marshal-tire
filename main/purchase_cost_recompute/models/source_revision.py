from odoo import api, models
from odoo.addons.pos_cost_recompute.models.source_revision import _touch


_PURCHASE_COST_SOURCES = {
    "purchase.order.line", "account.tax", "account.tax.repartition.line",
    "account.move", "account.move.line", "product.value", "stock.quant", "pos.order",
    "stock.scrap",
}


class PurchaseCostSourceRevision(models.AbstractModel):
    _inherit = "base"

    def _purchase_cost_source_products(self):
        """Resolve only parent IDs for the existing technical source version.

        A new child may be invisible to a correction's repeatable-read snapshot.
        Updating its already known product makes locking that product detect the
        concurrent transaction. Sudo resolves relation IDs only: the source's
        normal create/write/unlink access checks still govern the actual change.
        """
        source = self.sudo().with_context(active_test=False)
        products = self.env["product.product"]
        if self._name == "purchase.order.line":
            # A new line can introduce a product absent from the reader's
            # snapshot. Touch existing siblings, not just that new product.
            products = source.product_id | source.order_id.order_line.product_id
        elif self._name in {"account.tax", "account.tax.repartition.line"}:
            taxes = source if self._name == "account.tax" else source.tax_id
            products = taxes.purchase_order_line_ids.product_id
        elif self._name == "account.move":
            products = source.line_ids.purchase_line_id.product_id
            family = source._purchase_cost_document_family()
            products |= (family.pos_order_ids.lines.product_id
                         | family.line_ids.filtered(lambda line: line.display_type == "cogs").product_id)
        elif self._name == "account.move.line":
            products = source.purchase_line_id.product_id
            family = source.move_id._purchase_cost_document_family()
            products |= (family.pos_order_ids.lines.product_id
                         | source.filtered(lambda line: line.display_type == "cogs").product_id)
        elif self._name == "product.value":
            # Plain product-price history is not a manual stock-move valuation.
            products = source.move_id.product_id
        elif self._name == "stock.quant":
            products = source.product_id
        elif self._name == "stock.scrap":
            products = source.product_id | source.move_ids.product_id
        elif self._name == "pos.order":
            # Changing an existing draft to paid need not create any line or
            # stock move when the session defers its inventory processing.
            products = source.lines.product_id
        return products

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if self._name in _PURCHASE_COST_SOURCES:
            _touch(records._purchase_cost_source_products())
        return records

    def write(self, vals):
        before = (self._purchase_cost_source_products()
                  if self._name in _PURCHASE_COST_SOURCES else None)
        result = super().write(vals)
        if before is not None:
            _touch(before | self._purchase_cost_source_products())
        return result

    def unlink(self):
        before = (self._purchase_cost_source_products()
                  if self._name in _PURCHASE_COST_SOURCES else None)
        result = super().unlink()
        if before is not None:
            _touch(before.exists())
        return result


class AccountMove(models.Model):
    _inherit = "account.move"

    def _purchase_cost_document_family(self):
        """Resolve reversal links in batches, including hidden dependencies."""
        family = self.sudo().with_context(active_test=False)
        pending = family
        while pending:
            pending = (pending.reversed_entry_id | pending.reversal_move_ids) - family
            family |= pending
        return family


class ResCompany(models.Model):
    _inherit = "res.company"

    def _save_closing_id(self, move_id):
        result = super()._save_closing_id(move_id)
        # The first closing creates a configuration row invisible to an older
        # repeatable-read snapshot. Reuse the already locked currency version.
        _touch(self.currency_id)
        return result
