from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ua_nbu_qr_on_invoices = fields.Boolean(
        string="QR-код НБУ на рахунках",
        config_parameter='l10n_ua.nbu_qr_on_invoices',
        help="Додавати QR-код для оплати за стандартом НБУ на друковані рахунки-фактури",
    )
