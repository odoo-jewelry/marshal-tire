from odoo import _, api, fields, models
from odoo.fields import Domain
from odoo.exceptions import ValidationError


class ProductProduct(models.Model):
    _inherit = "product.product"

    alias_ids = fields.One2many(
        "product.identifier.alias", "product_id", string="Identifier Aliases"
    )

    @api.model
    def _resolve_identifier_batch(self, identifier_type, identifiers, company):
        if identifier_type not in ("default_code", "barcode"):
            raise ValidationError(_("Unsupported product identifier type."))
        # Alias rows are implementation metadata. Resolve them under sudo after
        # constraining company and return only products visible to the caller.
        Alias = self.env["product.identifier.alias"].sudo()
        original_by_normalized = {}
        for value in identifiers:
            normalized = Alias._normalize_identifier(value)
            if normalized:
                original_by_normalized.setdefault(normalized, []).append(value)
        result = {value: self.browse() for value in identifiers}
        if not original_by_normalized:
            return result
        products = self.with_company(company).search([
            ("active", "=", True),
            ("product_tmpl_id.company_id", "in", [False, company.id]),
            (identifier_type, "in", list(original_by_normalized)),
        ])
        for product in products:
            for original in original_by_normalized.get(product[identifier_type], []):
                result[original] |= product
        aliases = Alias.search([
            ("company_id", "in", [False, company.id]),
            ("identifier_type", "=", identifier_type),
            ("normalized_value", "in", list(original_by_normalized)),
            ("product_id.active", "=", True),
        ])
        for alias in aliases:
            for original in original_by_normalized[alias.normalized_value]:
                result[original] |= alias.product_id
        alias_product_ids = aliases.product_id.ids
        visible_alias_products = self.search([("id", "in", alias_product_ids)])
        allowed_product_ids = set(products.ids) | set(visible_alias_products.ids)
        for original, matched_products in result.items():
            result[original] = self.browse(
                [product_id for product_id in matched_products.ids if product_id in allowed_product_ids]
            )
        return result

    @api.model
    def _purchase_import_resolve_identifier_batch(
        self, identifier_type, identifiers, company
    ):
        return self._resolve_identifier_batch(identifier_type, identifiers, company)

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        results = super().name_search(name, domain, operator, limit)
        if not name or operator not in ("=", "ilike", "=ilike", "like", "=like"):
            return results
        alias_operator = "=" if operator == "=" else operator
        aliases = self.env["product.identifier.alias"].sudo().search([
            ("company_id", "in", [False, *self.env.companies.ids]),
            ("normalized_value", alias_operator, name.strip()),
            ("product_id.active", "=", True),
        ], limit=limit)
        existing_ids = {record_id for record_id, _display_name in results}
        remaining = None if not limit else max(limit - len(results), 0)
        if remaining == 0:
            return results
        alias_products = self.search(
            Domain.AND([
                Domain(domain or Domain.TRUE),
                Domain("id", "in", aliases.product_id.ids),
            ])
        )
        for product in alias_products:
            if product.id not in existing_ids:
                results.append((product.id, product.display_name))
                existing_ids.add(product.id)
                if limit and len(results) >= limit:
                    break
        return results

    @api.constrains("default_code", "barcode", "active", "product_tmpl_id")
    def _check_identifier_alias_conflicts(self):
        Alias = self.env["product.identifier.alias"]
        for product in self.filtered(lambda item: item.active):
            for identifier_type in ("default_code", "barcode"):
                value = Alias._normalize_identifier(product[identifier_type])
                if value and Alias.search_count([
                    ("company_id", "=", product.company_id.id),
                    ("identifier_type", "=", identifier_type),
                    ("normalized_value", "=", value),
                    ("product_id", "!=", product.id),
                ]):
                    raise ValidationError(
                        _("Identifier %(value)s is already preserved as an alias.", value=value)
                    )

    def write(self, vals):
        if vals.get("active") and any(self.mapped("product_tmpl_id.merged_into_id")):
            raise ValidationError(_("A variant of a consolidated product card cannot be unarchived."))
        return super().write(vals)
