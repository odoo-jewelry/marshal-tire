from odoo import api, fields, models


class L10nUaDeliveryMixin(models.AbstractModel):
    _name = 'l10n_ua.delivery.mixin'
    _description = 'Ukrainian Delivery Mixin'

    ua_carrier_type = fields.Selection(
        selection=[],
        string='UA Carrier Type',
    )

    def ua_create_shipment(self, picking):
        """Create shipment/TTN. Override in specific modules."""
        raise NotImplementedError()

    def ua_get_tracking(self, tracking_number):
        """Get tracking info. Override in specific modules."""
        raise NotImplementedError()

    def ua_calculate_cost(self, order):
        """Calculate delivery cost. Override in specific modules."""
        raise NotImplementedError()

    def ua_get_warehouses(self, city=None):
        """Get list of warehouses/branches. Override in specific modules."""
        raise NotImplementedError()

    def ua_print_label(self, picking):
        """Print shipping label. Override in specific modules."""
        raise NotImplementedError()
