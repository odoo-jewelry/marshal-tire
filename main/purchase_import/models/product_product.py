from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _purchase_import_resolve_identifier_batch(
        self, identifier_type, identifiers, company
    ):
        """Return active products keyed by the exact imported identifiers.

        Extensions can add durable identifier sources without coupling the
        purchase import addon to those extensions.
        """
        identifiers = {value for value in identifiers if value}
        result = {value: self.browse() for value in identifiers}
        if not identifiers:
            return result
        products = self.with_company(company).search([
            ("product_tmpl_id.company_id", "in", [False, company.id]),
            (identifier_type, "in", list(identifiers)),
        ])
        for product in products:
            value = product[identifier_type]
            result[value] |= product
        return result
