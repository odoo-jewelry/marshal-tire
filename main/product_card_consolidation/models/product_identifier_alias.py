from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProductIdentifierAlias(models.Model):
    _name = "product.identifier.alias"
    _description = "Product Identifier Alias"
    _order = "identifier_type, normalized_value, id"
    _check_company_auto = True

    product_id = fields.Many2one(
        "product.product",
        string="Canonical Product",
        required=True,
        ondelete="cascade",
        check_company=True,
        index=True,
    )
    source_product_id = fields.Many2one(
        "product.product",
        string="Source Product",
        ondelete="set null",
        index=True,
    )
    identifier_type = fields.Selection(
        [("default_code", "Internal Reference"), ("barcode", "Barcode")],
        required=True,
        index=True,
    )
    value = fields.Char(required=True)
    normalized_value = fields.Char(required=True, index=True)
    company_id = fields.Many2one(
        "res.company",
        ondelete="cascade",
        index=True,
    )

    _identifier_company_unique = models.UniqueIndex(
        "(identifier_type, normalized_value, COALESCE(company_id, 0))"
    )

    @api.model
    def _normalize_identifier(self, value):
        return value.strip() if isinstance(value, str) else value

    @api.model_create_multi
    def create(self, vals_list):
        self._check_consolidation_write()
        prepared = []
        for vals in vals_list:
            values = dict(vals)
            values["value"] = self._normalize_identifier(values.get("value"))
            values["normalized_value"] = self._normalize_identifier(
                values.get("normalized_value") or values.get("value")
            )
            prepared.append(values)
        aliases = super().create(prepared)
        aliases._check_identifier_conflicts()
        return aliases

    def write(self, vals):
        self._check_consolidation_write()
        values = dict(vals)
        if "value" in values:
            values["value"] = self._normalize_identifier(values["value"])
            values["normalized_value"] = values["value"]
        result = super().write(values)
        self._check_identifier_conflicts()
        return result

    def unlink(self):
        self._check_consolidation_write()
        return super().unlink()

    def _check_consolidation_write(self):
        if not self.env.context.get("product_consolidation_write"):
            raise AccessError(
                _("Identifier aliases can only be changed by product consolidation.")
            )

    @api.constrains(
        "product_id",
        "source_product_id",
        "identifier_type",
        "normalized_value",
        "company_id",
    )
    def _check_identifier_conflicts(self):
        Product = self.env["product.product"]
        Packaging = self.env["product.uom"]
        for alias in self:
            if not alias.normalized_value:
                raise ValidationError(_("A product identifier alias cannot be empty."))
            if alias.product_id.company_id != alias.company_id:
                raise ValidationError(_("The alias and canonical product must have the same company."))
            if alias.source_product_id and alias.source_product_id == alias.product_id:
                raise ValidationError(_("The alias source must differ from the canonical product."))
            direct_products = Product.search([
                ("active", "=", True),
                ("product_tmpl_id.company_id", "=", alias.company_id.id),
                (alias.identifier_type, "=", alias.normalized_value),
                ("id", "not in", (alias.product_id | alias.source_product_id).ids),
            ])
            if direct_products:
                raise ValidationError(
                    _("Identifier %(value)s is already used by another active product.", value=alias.value)
                )
            if alias.identifier_type == "barcode" and Packaging.search_count([
                ("barcode", "=", alias.normalized_value),
                ("company_id", "in", [False, alias.company_id.id]),
                ("product_id", "!=", alias.product_id.id),
            ]):
                raise ValidationError(
                    _("Barcode %(value)s is already used by a product unit.", value=alias.value)
                )
