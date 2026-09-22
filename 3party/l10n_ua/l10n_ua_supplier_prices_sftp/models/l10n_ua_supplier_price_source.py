from odoo import fields, models


class L10nUaSupplierPriceSource(models.Model):
    _inherit = 'l10n_ua.supplier.price.source'

    fetcher_type = fields.Selection(
        selection_add=[('sftp', 'SFTP')],
        ondelete={'sftp': 'set default'},
    )
