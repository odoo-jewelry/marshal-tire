from odoo import fields, models


class L10nUaSupplierPriceSource(models.Model):
    _inherit = 'l10n_ua.supplier.price.source'

    parser_type = fields.Selection(
        selection_add=[('xml', 'XML')],
        ondelete={'xml': 'set default'},
    )
