from odoo import api, fields, models, tools
from odoo.exceptions import AccessError
from odoo.tools import SQL


_REVISION = "consolidation_revision"


def touch_products(products):
    """Serialize source changes, including child inserts invisible to RR snapshots."""
    products = products.exists()
    if not products:
        return
    products.flush_recordset([_REVISION])
    # Technical metadata only; business ACLs were checked by the calling ORM hook.
    products.env.cr.execute(SQL(
        "UPDATE product_product SET consolidation_revision = COALESCE(consolidation_revision, 0) + 1 "
        "WHERE id IN (SELECT id FROM product_product WHERE id IN %s ORDER BY id FOR NO KEY UPDATE)",
        tuple(sorted(products.ids)),
    ))
    products.invalidate_recordset([_REVISION])


class ProductProduct(models.Model):
    _inherit = "product.product"

    consolidation_revision = fields.Integer(default=0, readonly=True, copy=False)


class HistorySourceRevision(models.AbstractModel):
    _inherit = "base"

    @tools.ormcache("self._name")
    def _history_product_reference_fields(self):
        if not self._auto or self._transient or self._name.startswith("product.consolidation."):
            return ()
        return tuple(name for name, field in self._fields.items()
                     if field.type in ("many2one", "many2many") and field.store and not field.related
                     and field.comodel_name in ("product.product", "product.template"))

    def _history_revision_products(self):
        products = self.env["product.product"].sudo().with_context(active_test=False)
        if not self:
            return products
        records = self.sudo().with_context(active_test=False)
        if self._name == "product.product":
            return records
        if self._name == "product.template":
            products |= records.product_variant_ids
        for name in self._history_product_reference_fields():
            references = records.mapped(name)
            products |= references if references._name == "product.product" else references.product_variant_ids
        for model, relation in (("stock.picking", "move_ids"), ("purchase.order", "order_line"),
                                ("sale.order", "order_line"), ("pos.order", "lines"),
                                ("account.move", "line_ids")):
            if self._name == model:
                products |= records.mapped(relation).product_id
        return products

    @api.model_create_multi
    def create(self, vals_list):
        if self._name == "product.product" and (
            any(_REVISION in vals for vals in vals_list) or "default_" + _REVISION in self.env.context
        ):
            raise AccessError(self.env._("Consolidation source versions are server-managed."))
        records = super().create(vals_list)
        touch_products(records._history_revision_products())
        return records

    def write(self, vals):
        if self._name == "product.product" and _REVISION in vals:
            raise AccessError(self.env._("Consolidation source versions are server-managed."))
        before = self._history_revision_products()
        result = super().write(vals)
        touch_products(before | self._history_revision_products())
        return result

    def unlink(self):
        products = self._history_revision_products()
        result = super().unlink()
        touch_products(products)
        return result
