from odoo import api, fields, models


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    np_api_url = fields.Char(
        string='API URL',
        default='https://api.novaposhta.ua/v2.0/json/',
    )

    def np_rate_shipment(self, order):
        """Calculate shipping cost via Nova Poshta API."""
        self.ensure_one()
        # TODO: Implement cost calculation
        return {
            'success': True,
            'price': 0.0,
            'error_message': False,
            'warning_message': False,
        }

    def np_send_shipping(self, pickings):
        """Create TTN via Nova Poshta API."""
        self.ensure_one()
        # TODO: Implement TTN creation
        return [{
            'exact_price': 0.0,
            'tracking_number': '',
        }]

    def np_get_tracking_link(self, picking):
        """Get tracking link."""
        return f'https://novaposhta.ua/tracking/?cargo_number={picking.carrier_tracking_ref}'

    def np_cancel_shipment(self, pickings):
        """Cancel TTN."""
        # TODO: Implement TTN cancellation
        pass

    def np_sync_warehouses(self):
        """Sync warehouses from Nova Poshta API."""
        self.ensure_one()
        # TODO: Implement warehouse sync
        pass
