from odoo import fields, models


class L10nUaSupplierPriceSource(models.Model):
    _inherit = 'l10n_ua.supplier.price.source'

    fetcher_type = fields.Selection(
        selection_add=[('api', 'HTTP API')],
        ondelete={'api': 'set default'},
    )
