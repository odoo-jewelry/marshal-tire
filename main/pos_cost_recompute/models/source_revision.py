from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import SQL


_REVISION = "cost_recompute_revision"
_PARENTS = {"product.product", "pos.order", "res.currency", "ir.module.module"}
_SOURCES = {
    "stock.move", "stock.move.line", "stock.picking", "pos.order.line",
    "pos.order", "res.currency.rate", "mrp.bom", "mrp.bom.line",
    "product.template",
}


def _touch(records):
    """Conflict on invisible child inserts, not just visible row changes.

    Atomic, sorted SQL increments avoid a read/modify/write race and update
    only technical metadata, without requiring business write rights on the
    parent. Callers are private ORM hooks; normal source ACLs still apply.
    No business fields, write_uid or write_date are changed.
    """
    if not records:
        return
    records.flush_recordset([_REVISION])
    records.env.cr.execute(SQL(
        "UPDATE %s SET %s = COALESCE(%s, 0) + 1 WHERE id IN "
        "(SELECT id FROM %s WHERE id IN %s ORDER BY id FOR NO KEY UPDATE)",
        SQL.identifier(records._table), SQL.identifier(_REVISION),
        SQL.identifier(_REVISION), SQL.identifier(records._table), tuple(sorted(records.ids)),
    ))
    records.invalidate_recordset([_REVISION])


class SourceRevision(models.AbstractModel):
    _inherit = "base"

    def _cost_recompute_source_parents(self):
        """Optional models are handled here without installing their addons."""
        products = self.env["product.product"]
        orders = self.env["pos.order"]
        currencies = self.env["res.currency"]
        if self._name == "stock.move":
            products = self.product_id | self.origin_returned_move_id.product_id
            orders = self.picking_id.pos_order_id
        elif self._name == "stock.move.line":
            products = self.product_id | self.move_id.product_id
        elif self._name == "stock.picking":
            products = self.move_ids.product_id
            orders = self.pos_order_id
        elif self._name == "pos.order.line":
            products = self.product_id | self.refunded_orderline_id.product_id
            orders = self.order_id | self.refunded_orderline_id.order_id
        elif self._name == "pos.order":
            if "correction_root_id" in self._fields:
                orders = self.correction_root_id
        elif self._name == "res.currency.rate":
            currencies = self.currency_id
        elif self._name in {"mrp.bom", "mrp.bom.line"}:
            boms = self if self._name == "mrp.bom" else self.bom_id
            products = boms.product_tmpl_id.with_context(active_test=False).product_variant_ids
        elif self._name == "product.template":
            # Inverse consolidation membership can be added without changing
            # the canonical card itself. Touch both old and new destinations.
            if "merged_into_id" in self._fields:
                products = self.merged_into_id.with_context(active_test=False).product_variant_ids
        return products, orders, currencies

    @api.model_create_multi
    def create(self, vals_list):
        if self._name in _PARENTS and (any(_REVISION in vals for vals in vals_list)
                                      or "default_" + _REVISION in self.env.context):
            raise AccessError(self.env._("Source versions are server-managed."))
        records = super().create(vals_list)
        if self._name in _SOURCES:
            for parents in records._cost_recompute_source_parents():
                _touch(parents)
        return records

    def write(self, vals):
        if self._name in _PARENTS and _REVISION in vals:
            raise AccessError(self.env._("Source versions are server-managed."))
        before = self._cost_recompute_source_parents() if self._name in _SOURCES else ()
        result = super().write(vals)
        if before:
            for old, new in zip(before, self._cost_recompute_source_parents()):
                _touch(old | new)
        return result

    def unlink(self):
        before = self._cost_recompute_source_parents() if self._name in _SOURCES else ()
        result = super().unlink()
        for parents in before:
            _touch(parents.exists())
        return result


class ProductProduct(models.Model):
    _inherit = "product.product"

    cost_recompute_revision = fields.Integer(default=0, readonly=True, copy=False)


class PosOrder(models.Model):
    _inherit = "pos.order"

    cost_recompute_revision = fields.Integer(default=0, readonly=True, copy=False)


class ResCurrency(models.Model):
    _inherit = "res.currency"

    cost_recompute_revision = fields.Integer(default=0, readonly=True, copy=False)
