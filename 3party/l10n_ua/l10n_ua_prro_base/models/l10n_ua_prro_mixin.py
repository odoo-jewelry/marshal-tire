from odoo import api, fields, models


class L10nUaPrroMixin(models.AbstractModel):
    _name = 'l10n_ua.prro.mixin'
    _description = 'PRRO Mixin'

    prro_provider = fields.Selection(
        selection=[],
        string='PRRO Provider',
        default=False,
    )

    def action_open_shift(self):
        """Open fiscal shift. Override in specific modules."""
        raise NotImplementedError()

    def action_close_shift(self):
        """Close fiscal shift (Z-report). Override in specific modules."""
        raise NotImplementedError()

    def action_x_report(self):
        """Generate X-report. Override in specific modules."""
        raise NotImplementedError()

    def action_register_receipt(self, receipt_data):
        """Register fiscal receipt. Override in specific modules."""
        raise NotImplementedError()

    def action_service_input(self, amount):
        """Service cash input. Override in specific modules."""
        raise NotImplementedError()

    def action_service_output(self, amount):
        """Service cash output. Override in specific modules."""
        raise NotImplementedError()
