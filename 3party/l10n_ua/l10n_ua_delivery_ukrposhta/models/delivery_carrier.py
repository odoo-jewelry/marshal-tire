from odoo import api, fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    def ukrposhta_rate_shipment(self, order):
        """Calculate shipping cost via Ukrposhta API."""
        self.ensure_one()
        # TODO: Implement cost calculation
        return {
            'success': True,
            'price': 0.0,
            'error_message': False,
            'warning_message': False,
        }

    def ukrposhta_send_shipping(self, pickings):
        """Create waybill via Ukrposhta API."""
        self.ensure_one()
        # TODO: Implement waybill creation
        return [{
            'exact_price': 0.0,
            'tracking_number': '',
        }]

    def ukrposhta_get_tracking_link(self, picking):
        """Get tracking link."""
        return f'https://track.ukrposhta.ua/tracking_UA.html?barcode={picking.carrier_tracking_ref}'

    def ukrposhta_cancel_shipment(self, pickings):
        """Cancel waybill."""
        # TODO: Implement cancellation
        pass

    def ukrposhta_sync_branches(self):
        """Sync branches from Ukrposhta API."""
        self.ensure_one()
        # TODO: Implement branch sync
        pass
