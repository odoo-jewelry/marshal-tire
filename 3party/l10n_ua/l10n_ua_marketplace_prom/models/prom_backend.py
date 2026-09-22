import hashlib
import hmac
import json
import logging
import requests
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

PROM_API_URL = 'https://my.prom.ua/api/v1'

# Prom.ua specific cancel reasons
PROM_CANCEL_REASONS = [
    ('not_available', 'Product not available'),
    ('price_changed', 'Price changed'),
    ('out_of_stock', 'Out of stock'),
    ('buyer_refused', 'Buyer refused'),
    ('incorrect_data', 'Incorrect order data'),
    ('duplicate', 'Duplicate order'),
    ('other', 'Other'),
]


class MarketplaceBackendProm(models.Model):
    _inherit = 'marketplace.backend'

    # === Prom.ua Specific Fields ===
    prom_company_id = fields.Char(
        string='Company ID',
        help='Your Prom.ua Company ID',
    )

    @api.model
    def _selection_marketplace_type(self):
        """Add prom to available marketplace types."""
        res = super()._selection_marketplace_type()
        if ('prom', 'Prom.ua') not in res:
            res.append(('prom', 'Prom.ua'))
        return res

    @api.onchange('marketplace_type')
    def _onchange_marketplace_type_prom(self):
        """Set default API URL for Prom.ua."""
        if self.marketplace_type == 'prom' and not self.api_url:
            self.api_url = PROM_API_URL

    # === API Request Helper ===
    def _prom_api_request(self, method, endpoint, data=None, params=None):
        """Make authenticated request to Prom.ua API."""
        self.ensure_one()
        url = f'{self.api_url or PROM_API_URL}{endpoint}'

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=60,
            )

            if response.status_code == 401:
                raise UserError(_('Prom.ua API authentication failed. Check your API key.'))

            response.raise_for_status()

            if response.content:
                return response.json()
            return {}

        except requests.exceptions.RequestException as e:
            _logger.error(f"Prom.ua API error: {e}")
            raise UserError(_('Prom.ua API error: %s') % str(e))

    # === Connection Test ===
    def action_test_connection(self):
        """Test Prom.ua API connection."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super().action_test_connection()

        try:
            # Try to get company info
            result = self._prom_api_request('GET', '/cabinet/company')

            if result.get('id'):
                self.prom_company_id = str(result['id'])
                self._clear_error()
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Successfully connected to Prom.ua API. Company: %s') % result.get('name', ''),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                raise UserError(_('Invalid API response from Prom.ua'))

        except Exception as e:
            self._set_error(str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def _api_authenticate(self):
        """Prom.ua uses static API token, no refresh needed."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._api_authenticate()
        # Prom uses static Bearer token, no auth flow needed
        return self.api_key

    def action_refresh_token(self):
        """Prom.ua uses static token."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super().action_refresh_token()
        # No token refresh for Prom
        return True

    # === Order Import ===
    def _api_get_orders(self, from_date=None):
        """Get orders from Prom.ua API."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._api_get_orders(from_date)

        params = {
            'limit': 100,
        }

        if from_date:
            params['date_from'] = from_date.strftime('%Y-%m-%d')
        elif self.import_orders_from_date:
            params['date_from'] = self.import_orders_from_date.strftime('%Y-%m-%d')

        all_orders = []
        offset = 0

        while True:
            params['offset'] = offset
            result = self._prom_api_request('GET', '/orders/list', params=params)

            orders = result.get('orders', [])
            if not orders:
                break

            all_orders.extend(orders)

            if len(orders) < params['limit']:
                break

            offset += params['limit']

        return all_orders

    def _import_orders(self):
        """Import orders from Prom.ua."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._import_orders()

        from_date = self.import_orders_last or self.import_orders_from_date
        orders_data = self._api_get_orders(from_date)

        count = 0
        Order = self.env['marketplace.order']

        for order_data in orders_data:
            external_id = str(order_data.get('id'))

            existing = Order.search([
                ('backend_id', '=', self.id),
                ('external_id', '=', external_id),
            ], limit=1)

            if existing:
                existing._update_from_prom(order_data)
                continue

            order_vals = self._prepare_prom_order_vals(order_data)
            order = Order.create(order_vals)
            order._create_lines_from_prom(order_data.get('products', []))
            count += 1

            if self.auto_create_sale_order:
                try:
                    order.action_create_sale_order()
                    if self.auto_confirm_sale_order and order.sale_order_id:
                        order.sale_order_id.action_confirm()
                except Exception as e:
                    _logger.warning(f"Failed to create sale order: {e}")

        self.import_orders_last = fields.Datetime.now()
        _logger.info(f"Imported {count} orders from Prom.ua for {self.name}")
        return count

    def _prepare_prom_order_vals(self, data):
        """Prepare order values from Prom.ua data."""
        delivery = data.get('delivery_option', {}) or {}
        client = data.get('client', {}) or {}

        # Map Prom.ua status to internal status
        status_map = {
            'pending': 'new',
            'received': 'confirmed',
            'delivered': 'delivered',
            'canceled': 'cancelled',
            'draft': 'new',
            'paid': 'processing',
        }

        order_date = data.get('date_created')
        if order_date:
            # Parse ISO format
            try:
                order_date = datetime.fromisoformat(order_date.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                order_date = fields.Datetime.now()

        # Build delivery address
        delivery_address_parts = []
        if data.get('delivery_address'):
            delivery_address_parts.append(data['delivery_address'])

        return {
            'backend_id': self.id,
            'external_id': str(data.get('id')),
            'name': f"PROM-{data.get('id')}",
            'order_date': order_date,
            'marketplace_state': data.get('status'),
            'state': status_map.get(data.get('status'), 'new'),
            'amount_total': float(data.get('price', 0)),
            'amount_delivery': float(data.get('delivery_cost', 0) or 0),
            'customer_name': client.get('name') or f"{client.get('first_name', '')} {client.get('last_name', '')}".strip(),
            'customer_phone': client.get('phone') or client.get('phones', [''])[0] if client.get('phones') else '',
            'customer_email': client.get('email') or (client.get('emails', [''])[0] if client.get('emails') else ''),
            'customer_comment': data.get('client_notes'),
            'delivery_method': delivery.get('name'),
            'delivery_carrier_name': delivery.get('delivery_service_name'),
            'delivery_city': data.get('delivery_city_name'),
            'delivery_address': '\n'.join(filter(None, delivery_address_parts)) or data.get('delivery_address'),
            'delivery_warehouse': data.get('delivery_branch_number'),
            'tracking_number': data.get('cpa_commission', {}).get('ttn') if isinstance(data.get('cpa_commission'), dict) else None,
            'payment_method': data.get('payment_option', {}).get('name') if isinstance(data.get('payment_option'), dict) else None,
            'is_paid': data.get('status') == 'paid',
            'raw_data': json.dumps(data, ensure_ascii=False, indent=2),
        }

    # === Order Status Update ===
    def _api_update_order_status(self, order, status, tracking=None):
        """Update order status on Prom.ua."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._api_update_order_status(order, status, tracking)

        # Map internal status to Prom.ua status
        status_map = {
            'confirmed': 'received',
            'shipped': 'delivered',
            'delivered': 'delivered',
            'cancelled': 'canceled',
        }

        prom_status = status_map.get(status)
        if not prom_status:
            return False

        data = {
            'status': prom_status,
        }

        # Add tracking number for shipped status
        if tracking and status == 'shipped':
            data['delivery_type'] = 'nova_poshta'  # Default carrier
            data['ttn'] = tracking

        try:
            self._prom_api_request(
                'POST',
                f'/orders/{order.external_id}/set_status',
                data=data,
            )
            return True
        except Exception as e:
            _logger.error(f"Failed to update Prom.ua order status: {e}")
            return False

    # === Stock Sync ===
    def _sync_stock(self):
        """Sync stock to Prom.ua."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._sync_stock()

        items = self.env['marketplace.pricelist.item'].search([
            ('backend_id', '=', self.id),
            ('state', 'in', ['published', 'pending']),
            ('active', '=', True),
            ('external_id', '!=', False),
        ])

        if not items:
            return

        # Prom.ua uses product editing for stock updates
        for item in items:
            try:
                self._prom_api_request(
                    'POST',
                    f'/products/{item.external_id}/edit',
                    data={
                        'quantity_in_stock': int(item.qty_to_publish),
                        'presence': 'available' if item.qty_to_publish > 0 else 'not_available',
                    },
                )
                item.write({
                    'last_sync': fields.Datetime.now(),
                    'sync_error': False,
                })
            except Exception as e:
                _logger.error(f"Failed to sync stock for product {item.external_id}: {e}")
                item.write({
                    'sync_error': str(e),
                })

        self.sync_stock_last = fields.Datetime.now()

    # === Price Sync ===
    def _sync_prices(self):
        """Sync prices to Prom.ua."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._sync_prices()

        items = self.env['marketplace.pricelist.item'].search([
            ('backend_id', '=', self.id),
            ('state', 'in', ['published', 'pending']),
            ('active', '=', True),
            ('external_id', '!=', False),
        ])

        if not items:
            return

        for item in items:
            try:
                data = {
                    'price': item.price,
                }
                if item.price_original and item.price_original > item.price:
                    data['discount'] = {
                        'type': 'amount',
                        'value': item.price_original - item.price,
                    }

                self._prom_api_request(
                    'POST',
                    f'/products/{item.external_id}/edit',
                    data=data,
                )
                item.write({
                    'last_sync': fields.Datetime.now(),
                    'sync_error': False,
                })
            except Exception as e:
                _logger.error(f"Failed to sync price for product {item.external_id}: {e}")
                item.write({
                    'sync_error': str(e),
                })

        self.sync_prices_last = fields.Datetime.now()

    # === Batch Stock Sync ===
    def _api_sync_stock_batch(self, items):
        """Batch stock update via Prom.ua API."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._api_sync_stock_batch(items)

        if not items:
            return

        # Build batch payload
        products_data = []
        for item in items:
            products_data.append({
                'id': int(item.external_id),
                'presence': 'available' if item.qty_to_publish > 0 else 'not_available',
                'quantity_in_stock': int(item.qty_to_publish),
            })

        try:
            # Single API call for batch update
            self._prom_api_request(
                'POST',
                '/products/edit',
                data=products_data,
            )

            # Update sync timestamps
            items.write({
                'last_sync': fields.Datetime.now(),
                'sync_error': False,
            })
            _logger.info(f"Batch stock sync: updated {len(items)} items on Prom.ua")

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Batch stock sync failed: {error_msg}")

            # Handle based on error handling strategy
            if self.sync_error_handling == 'continue':
                items.write({'sync_error': error_msg})
            elif self.sync_error_handling == 'retry':
                # Fallback to individual sync
                for item in items:
                    try:
                        self._prom_api_request(
                            'POST',
                            f'/products/{item.external_id}/edit',
                            data={
                                'quantity_in_stock': int(item.qty_to_publish),
                                'presence': 'available' if item.qty_to_publish > 0 else 'not_available',
                            },
                        )
                        item.write({'last_sync': fields.Datetime.now(), 'sync_error': False})
                    except Exception as item_error:
                        item.write({'sync_error': str(item_error)})
            else:  # stop
                items.write({'sync_error': error_msg})
                raise

    # === Batch Price Sync ===
    def _api_sync_prices_batch(self, items):
        """Batch price update via Prom.ua API."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._api_sync_prices_batch(items)

        if not items:
            return

        # Build batch payload
        products_data = []
        for item in items:
            product_data = {
                'id': int(item.external_id),
                'price': item.price,
            }
            # Add discount if original price is higher
            if item.price_original and item.price_original > item.price:
                product_data['discount'] = {
                    'type': 'amount',
                    'value': item.price_original - item.price,
                }
            products_data.append(product_data)

        try:
            self._prom_api_request(
                'POST',
                '/products/edit',
                data=products_data,
            )

            items.write({
                'last_sync': fields.Datetime.now(),
                'sync_error': False,
            })
            _logger.info(f"Batch price sync: updated {len(items)} items on Prom.ua")

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Batch price sync failed: {error_msg}")

            if self.sync_error_handling == 'continue':
                items.write({'sync_error': error_msg})
            elif self.sync_error_handling == 'retry':
                for item in items:
                    try:
                        data = {'price': item.price}
                        if item.price_original and item.price_original > item.price:
                            data['discount'] = {
                                'type': 'amount',
                                'value': item.price_original - item.price,
                            }
                        self._prom_api_request(
                            'POST',
                            f'/products/{item.external_id}/edit',
                            data=data,
                        )
                        item.write({'last_sync': fields.Datetime.now(), 'sync_error': False})
                    except Exception as item_error:
                        item.write({'sync_error': str(item_error)})
            else:  # stop
                items.write({'sync_error': error_msg})
                raise

    # === Status Mapping Sync ===
    def action_sync_statuses(self):
        """Sync order statuses from Prom.ua API."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super().action_sync_statuses()

        # Prom.ua order status options
        prom_statuses = [
            ('pending', 'Новый', 'new'),
            ('received', 'Принят', 'confirmed'),
            ('delivered', 'Доставлен', 'delivered'),
            ('canceled', 'Отменен', 'cancelled'),
            ('paid', 'Оплачен', 'processing'),
        ]

        StatusMapping = self.env['marketplace.status.mapping']
        count = 0

        for external_code, external_name, internal_state in prom_statuses:
            existing = StatusMapping.search([
                ('backend_id', '=', self.id),
                ('external_code', '=', external_code),
            ], limit=1)

            if not existing:
                StatusMapping.create({
                    'backend_id': self.id,
                    'external_code': external_code,
                    'external_name': external_name,
                    'internal_state': internal_state,
                    'sync_to_marketplace': True,
                    'sync_from_marketplace': True,
                })
                count += 1
            else:
                existing.write({
                    'external_name': external_name,
                    'internal_state': internal_state,
                })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Status Mapping'),
                'message': _('%d status mappings created/updated for Prom.ua.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    # === Order Cancellation ===
    def _api_cancel_order(self, order, reason=None, comment=None):
        """Cancel order on Prom.ua."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._api_cancel_order(order, reason, comment)

        # Map cancel reasons
        prom_reason_map = {
            'customer_request': 'buyer_refused',
            'out_of_stock': 'out_of_stock',
            'pricing_error': 'price_changed',
            'duplicate_order': 'duplicate',
            'fraud_suspicion': 'other',
            'delivery_issue': 'other',
            'other': 'other',
        }

        data = {
            'status': 'canceled',
        }

        # Add cancellation reason if supported
        cancellation_reason = prom_reason_map.get(reason, 'other')
        if cancellation_reason:
            data['cancellation_reason'] = cancellation_reason

        if comment:
            data['cancellation_text'] = comment

        try:
            self._prom_api_request(
                'POST',
                f'/orders/{order.external_id}/set_status',
                data=data,
            )
            _logger.info(f"Order {order.name} cancelled on Prom.ua")
            return True
        except Exception as e:
            _logger.error(f"Failed to cancel order {order.name} on Prom.ua: {e}")
            raise UserError(_('Failed to cancel order on Prom.ua: %s') % str(e))

    # === Product Import from Prom ===
    def action_import_products(self):
        """Import products from Prom.ua to pricelist items."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            raise UserError(_('This action is only available for Prom.ua backends.'))

        params = {'limit': 100}
        all_products = []
        offset = 0

        while True:
            params['offset'] = offset
            result = self._prom_api_request('GET', '/products/list', params=params)
            products = result.get('products', [])
            if not products:
                break
            all_products.extend(products)
            if len(products) < params['limit']:
                break
            offset += params['limit']

        # Find or create pricelist
        pricelist = self.feed_pricelist_id
        if not pricelist:
            pricelist = self.env['marketplace.pricelist'].create({
                'name': f'{self.name} - Products',
                'backend_id': self.id,
            })
            self.feed_pricelist_id = pricelist

        count = 0
        Item = self.env['marketplace.pricelist.item']

        for prod_data in all_products:
            external_id = str(prod_data.get('id'))

            existing = Item.search([
                ('pricelist_id', '=', pricelist.id),
                ('external_id', '=', external_id),
            ], limit=1)

            if existing:
                continue

            # Try to find matching Odoo product
            product = None
            sku = prod_data.get('sku')
            if sku:
                product = self.env['product.template'].search([
                    ('default_code', '=', sku),
                ], limit=1)

            Item.create({
                'pricelist_id': pricelist.id,
                'external_id': external_id,
                'product_tmpl_id': product.id if product else False,
                'sku': sku,
                'name_override': prod_data.get('name'),
                'price': float(prod_data.get('price', 0)),
                'qty_available': float(prod_data.get('quantity_in_stock', 0) or 0),
                'state': 'published' if prod_data.get('presence') == 'available' else 'draft',
            })
            count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Products Imported'),
                'message': _('%d products imported from Prom.ua.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    # === Webhook Handling ===
    def _process_webhook(self, data, headers=None):
        """Process incoming Prom.ua webhook."""
        self.ensure_one()
        if self.marketplace_type != 'prom':
            return super()._process_webhook(data, headers)

        event_type = data.get('event_type')

        if event_type in ('order_created', 'new_order'):
            order_data = data.get('order', data.get('data', {}))
            if order_data:
                external_id = str(order_data.get('id'))
                existing = self.env['marketplace.order'].search([
                    ('backend_id', '=', self.id),
                    ('external_id', '=', external_id),
                ], limit=1)

                if not existing:
                    order_vals = self._prepare_prom_order_vals(order_data)
                    order = self.env['marketplace.order'].create(order_vals)
                    order._create_lines_from_prom(order_data.get('products', []))

                    if self.auto_create_sale_order:
                        try:
                            order.action_create_sale_order()
                            if self.auto_confirm_sale_order and order.sale_order_id:
                                order.sale_order_id.action_confirm()
                        except Exception as e:
                            _logger.warning(f"Failed to create sale order: {e}")

        elif event_type in ('order_status_changed', 'status_changed'):
            order_data = data.get('order', data.get('data', {}))
            external_id = str(order_data.get('id'))
            order = self.env['marketplace.order'].search([
                ('backend_id', '=', self.id),
                ('external_id', '=', external_id),
            ], limit=1)
            if order:
                order._update_from_prom(order_data)

        return True


class MarketplaceOrderProm(models.Model):
    _inherit = 'marketplace.order'

    def _update_from_prom(self, data):
        """Update order from Prom.ua data."""
        self.ensure_one()

        status_map = {
            'pending': 'new',
            'received': 'confirmed',
            'delivered': 'delivered',
            'canceled': 'cancelled',
            'draft': 'new',
            'paid': 'processing',
        }

        vals = {
            'marketplace_state': data.get('status'),
            'state': status_map.get(data.get('status'), self.state),
        }

        if data.get('status') == 'paid':
            vals['is_paid'] = True

        self.write(vals)

    def _create_lines_from_prom(self, products_data):
        """Create order lines from Prom.ua products data."""
        self.ensure_one()
        Line = self.env['marketplace.order.line']

        for item in products_data:
            product = None
            sku = item.get('sku') or item.get('external_id')

            if sku:
                product = self.env['product.product'].search([
                    '|',
                    ('default_code', '=', sku),
                    ('barcode', '=', sku),
                ], limit=1)

            Line.create({
                'order_id': self.id,
                'external_id': str(item.get('id', '')),
                'product_id': product.id if product else False,
                'sku': sku,
                'name': item.get('name', 'Unknown Product'),
                'quantity': float(item.get('quantity', 1)),
                'price_unit': float(item.get('price', 0)),
                'discount': float(item.get('discount', 0) or 0),
                'price_total': float(item.get('total_price', 0) or (item.get('price', 0) * item.get('quantity', 1))),
            })


class MarketplaceOrderCancelWizardProm(models.TransientModel):
    """Extend cancel wizard with Prom-specific cancel reasons."""
    _inherit = 'marketplace.order.cancel.wizard'

    @api.model
    def _get_cancel_reasons(self):
        """Override to add Prom-specific cancel reasons when applicable."""
        reasons = super()._get_cancel_reasons()

        # Check if any order is from Prom.ua
        order_ids = self.env.context.get('default_order_ids')
        if order_ids:
            orders = self.env['marketplace.order'].browse(
                order_ids[0][2] if isinstance(order_ids[0], (list, tuple)) else order_ids
            )
            if any(o.marketplace_type == 'prom' for o in orders):
                # Return Prom-specific reasons
                return PROM_CANCEL_REASONS

        return reasons
