import hashlib
import hmac
import json
import logging
import requests
from datetime import datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

ROZETKA_API_URL = 'https://api-seller.rozetka.com.ua'

# Rozetka specific cancel reasons
ROZETKA_CANCEL_REASONS = [
    ('out_of_stock', 'Out of Stock'),
    ('price_error', 'Price Error'),
    ('customer_request', 'Customer Request'),
    ('duplicate', 'Duplicate Order'),
    ('cannot_deliver', 'Cannot Deliver'),
    ('defective_product', 'Defective Product'),
    ('other', 'Other'),
]


class MarketplaceBackendRozetka(models.Model):
    _inherit = 'marketplace.backend'

    # === Rozetka Specific Fields ===
    rozetka_seller_id = fields.Char(
        string='Seller ID',
        help='Your Rozetka Seller ID',
    )
    rozetka_client_id = fields.Char(
        string='Client ID',
        groups='base.group_system',
    )
    rozetka_username = fields.Char(
        string='Username',
        help='Login for Rozetka Seller Portal',
    )
    rozetka_password = fields.Char(
        string='Password',
        groups='base.group_system',
    )

    @api.model
    def _selection_marketplace_type(self):
        """Add rozetka to available marketplace types."""
        res = super()._selection_marketplace_type()
        if ('rozetka', 'Rozetka') not in res:
            res.append(('rozetka', 'Rozetka'))
        return res

    # === API Authentication ===
    def _api_authenticate(self):
        """Authenticate with Rozetka API and get access token."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._api_authenticate()

        url = f'{ROZETKA_API_URL}/sites'

        # Rozetka uses username/password for initial auth
        payload = {
            'username': self.rozetka_username or self.api_key,
            'password': self.rozetka_password or self.api_secret,
        }

        try:
            response = requests.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            if data.get('success') and data.get('content', {}).get('access_token'):
                token = data['content']['access_token']
                # Rozetka tokens are valid for 24 hours
                expiry = fields.Datetime.now() + timedelta(hours=23)
                self.write({
                    'api_token': token,
                    'api_token_expiry': expiry,
                })
                self._clear_error()
                return token
            else:
                error_msg = data.get('errors', {}).get('message', 'Unknown error')
                raise UserError(_('Rozetka authentication failed: %s') % error_msg)

        except requests.exceptions.RequestException as e:
            self._set_error(str(e))
            raise UserError(_('Rozetka API connection error: %s') % str(e))

    def _get_rozetka_headers(self):
        """Get headers for Rozetka API requests."""
        self.ensure_one()
        if not self.api_token or (self.api_token_expiry and self.api_token_expiry < fields.Datetime.now()):
            self._api_authenticate()
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

    def _rozetka_api_request(self, method, endpoint, data=None, params=None):
        """Make authenticated request to Rozetka API."""
        self.ensure_one()
        url = f'{ROZETKA_API_URL}{endpoint}'
        headers = self._get_rozetka_headers()

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data,
                params=params,
                timeout=60,
            )

            # Handle token expiration
            if response.status_code == 401:
                self._api_authenticate()
                headers = self._get_rozetka_headers()
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=data,
                    params=params,
                    timeout=60,
                )

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            _logger.error(f"Rozetka API error: {e}")
            raise UserError(_('Rozetka API error: %s') % str(e))

    # === Connection Test ===
    def action_test_connection(self):
        """Test Rozetka API connection."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super().action_test_connection()

        try:
            self._api_authenticate()
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _('Successfully connected to Rozetka Seller API.'),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
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

    def action_refresh_token(self):
        """Refresh Rozetka API token."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super().action_refresh_token()
        return self._api_authenticate()

    # === Order Import ===
    def _api_get_orders(self, from_date=None):
        """Get orders from Rozetka API."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._api_get_orders(from_date)

        params = {
            'expand': 'items,delivery,payment',
            'per-page': 100,
        }

        if from_date:
            params['created_from'] = from_date.strftime('%Y-%m-%d')
        elif self.import_orders_from_date:
            params['created_from'] = self.import_orders_from_date.strftime('%Y-%m-%d')

        all_orders = []
        page = 1

        while True:
            params['page'] = page
            result = self._rozetka_api_request('GET', '/orders', params=params)

            if not result.get('success'):
                break

            orders = result.get('content', {}).get('orders', [])
            if not orders:
                break

            all_orders.extend(orders)

            # Check pagination
            pagination = result.get('content', {}).get('_meta', {})
            if page >= pagination.get('pageCount', 1):
                break
            page += 1

        return all_orders

    def _import_orders(self):
        """Import orders from Rozetka."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._import_orders()

        from_date = self.import_orders_last or self.import_orders_from_date
        orders_data = self._api_get_orders(from_date)

        count = 0
        Order = self.env['marketplace.order']

        for order_data in orders_data:
            external_id = str(order_data.get('id'))

            # Check if order already exists
            existing = Order.search([
                ('backend_id', '=', self.id),
                ('external_id', '=', external_id),
            ], limit=1)

            if existing:
                # Update status if changed
                existing._update_from_rozetka(order_data)
                continue

            # Create new order
            order_vals = self._prepare_rozetka_order_vals(order_data)
            order = Order.create(order_vals)
            order._create_lines_from_rozetka(order_data.get('items', []))
            count += 1

            # Auto create sale order if configured
            if self.auto_create_sale_order:
                try:
                    order.action_create_sale_order()
                    if self.auto_confirm_sale_order and order.sale_order_id:
                        order.sale_order_id.action_confirm()
                except Exception as e:
                    _logger.warning(f"Failed to create sale order: {e}")

        self.import_orders_last = fields.Datetime.now()
        _logger.info(f"Imported {count} orders from Rozetka for {self.name}")
        return count

    def _prepare_rozetka_order_vals(self, data):
        """Prepare order values from Rozetka data."""
        delivery = data.get('delivery', {})
        user_info = data.get('user', {}) or {}

        # Map Rozetka status to internal status
        status_map = {
            1: 'new',           # Новый
            2: 'confirmed',     # Принят
            3: 'processing',    # Комплектуется
            4: 'shipped',       # Отправлен
            5: 'delivered',     # Доставлен
            6: 'cancelled',     # Отменен
            7: 'returned',      # Возврат
        }

        return {
            'backend_id': self.id,
            'external_id': str(data.get('id')),
            'name': f"RZ-{data.get('id')}",
            'order_date': data.get('created_at'),
            'marketplace_state': str(data.get('status')),
            'state': status_map.get(data.get('status'), 'new'),
            'amount_total': float(data.get('amount', 0)),
            'amount_delivery': float(data.get('delivery_cost', 0)),
            'commission_amount': float(data.get('commission', 0)),
            'customer_name': f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
            'customer_phone': user_info.get('phone'),
            'customer_email': user_info.get('email'),
            'delivery_method': delivery.get('delivery_service_name'),
            'delivery_carrier_name': delivery.get('delivery_service_name'),
            'delivery_city': delivery.get('city', {}).get('name') if isinstance(delivery.get('city'), dict) else delivery.get('city'),
            'delivery_address': delivery.get('place_street'),
            'delivery_warehouse': delivery.get('place_number'),
            'tracking_number': delivery.get('ttn'),
            'payment_method': data.get('payment_type'),
            'is_paid': data.get('is_paid', False),
            'raw_data': json.dumps(data, ensure_ascii=False, indent=2),
        }

    # === Order Status Update ===
    def _api_update_order_status(self, order, status, tracking=None):
        """Update order status on Rozetka."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._api_update_order_status(order, status, tracking)

        # Map internal status to Rozetka status
        status_map = {
            'confirmed': 2,
            'processing': 3,
            'shipped': 4,
            'delivered': 5,
            'cancelled': 6,
        }

        rozetka_status = status_map.get(status)
        if not rozetka_status:
            return False

        data = {
            'status': rozetka_status,
        }

        if tracking:
            data['ttn'] = tracking

        try:
            result = self._rozetka_api_request(
                'PUT',
                f'/orders/{order.external_id}',
                data=data,
            )
            return result.get('success', False)
        except Exception as e:
            _logger.error(f"Failed to update Rozetka order status: {e}")
            return False

    # === Stock Sync ===
    def _sync_stock(self):
        """Sync stock to Rozetka."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._sync_stock()

        items = self.env['marketplace.pricelist.item'].search([
            ('backend_id', '=', self.id),
            ('state', 'in', ['published', 'pending']),
            ('active', '=', True),
        ])

        if not items:
            return

        # Rozetka accepts batch stock updates
        stock_data = []
        for item in items:
            stock_data.append({
                'id': item.external_id,
                'stock': int(item.qty_to_publish),
            })

        # Rozetka limits batch size
        batch_size = 100
        for i in range(0, len(stock_data), batch_size):
            batch = stock_data[i:i + batch_size]
            try:
                self._rozetka_api_request(
                    'PUT',
                    '/items/stock',
                    data={'items': batch},
                )
            except Exception as e:
                _logger.error(f"Failed to sync stock batch: {e}")

        self.sync_stock_last = fields.Datetime.now()

    # === Price Sync ===
    def _sync_prices(self):
        """Sync prices to Rozetka."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._sync_prices()

        items = self.env['marketplace.pricelist.item'].search([
            ('backend_id', '=', self.id),
            ('state', 'in', ['published', 'pending']),
            ('active', '=', True),
        ])

        if not items:
            return

        price_data = []
        for item in items:
            price_data.append({
                'id': item.external_id,
                'price': item.price,
                'old_price': item.price_original if item.price_original > item.price else None,
            })

        batch_size = 100
        for i in range(0, len(price_data), batch_size):
            batch = price_data[i:i + batch_size]
            try:
                self._rozetka_api_request(
                    'PUT',
                    '/items/prices',
                    data={'items': batch},
                )
            except Exception as e:
                _logger.error(f"Failed to sync prices batch: {e}")

        self.sync_prices_last = fields.Datetime.now()

    # === Batch Stock Sync ===
    def _api_sync_stock_batch(self, items):
        """Batch stock update via Rozetka API."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._api_sync_stock_batch(items)

        if not items:
            return

        # Build batch payload
        stock_data = []
        for item in items:
            if item.external_id:
                stock_data.append({
                    'id': item.external_id,
                    'stock': int(item.qty_to_publish),
                })

        if not stock_data:
            return

        try:
            self._rozetka_api_request(
                'PUT',
                '/items/stock',
                data={'items': stock_data},
            )

            items.write({
                'last_sync': fields.Datetime.now(),
                'sync_error': False,
            })
            _logger.info(f"Batch stock sync: updated {len(items)} items on Rozetka")

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Batch stock sync failed: {error_msg}")

            if self.sync_error_handling == 'continue':
                items.write({'sync_error': error_msg})
            elif self.sync_error_handling == 'retry':
                # Fallback to individual updates
                for item in items:
                    try:
                        self._rozetka_api_request(
                            'PUT',
                            '/items/stock',
                            data={'items': [{'id': item.external_id, 'stock': int(item.qty_to_publish)}]},
                        )
                        item.write({'last_sync': fields.Datetime.now(), 'sync_error': False})
                    except Exception as item_error:
                        item.write({'sync_error': str(item_error)})
            else:  # stop
                items.write({'sync_error': error_msg})
                raise

    # === Batch Price Sync ===
    def _api_sync_prices_batch(self, items):
        """Batch price update via Rozetka API."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._api_sync_prices_batch(items)

        if not items:
            return

        # Build batch payload
        price_data = []
        for item in items:
            if item.external_id:
                item_data = {
                    'id': item.external_id,
                    'price': item.price,
                }
                if item.price_original and item.price_original > item.price:
                    item_data['old_price'] = item.price_original
                price_data.append(item_data)

        if not price_data:
            return

        try:
            self._rozetka_api_request(
                'PUT',
                '/items/prices',
                data={'items': price_data},
            )

            items.write({
                'last_sync': fields.Datetime.now(),
                'sync_error': False,
            })
            _logger.info(f"Batch price sync: updated {len(items)} items on Rozetka")

        except Exception as e:
            error_msg = str(e)
            _logger.error(f"Batch price sync failed: {error_msg}")

            if self.sync_error_handling == 'continue':
                items.write({'sync_error': error_msg})
            elif self.sync_error_handling == 'retry':
                for item in items:
                    try:
                        data = {'id': item.external_id, 'price': item.price}
                        if item.price_original and item.price_original > item.price:
                            data['old_price'] = item.price_original
                        self._rozetka_api_request(
                            'PUT',
                            '/items/prices',
                            data={'items': [data]},
                        )
                        item.write({'last_sync': fields.Datetime.now(), 'sync_error': False})
                    except Exception as item_error:
                        item.write({'sync_error': str(item_error)})
            else:  # stop
                items.write({'sync_error': error_msg})
                raise

    # === Status Mapping Sync ===
    def action_sync_statuses(self):
        """Sync order statuses from Rozetka API."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super().action_sync_statuses()

        # Rozetka order statuses (numeric codes)
        rozetka_statuses = [
            ('1', 'Новый', 'new'),
            ('2', 'Принят', 'confirmed'),
            ('3', 'Комплектуется', 'processing'),
            ('4', 'Отправлен', 'shipped'),
            ('5', 'Доставлен', 'delivered'),
            ('6', 'Отменен', 'cancelled'),
            ('7', 'Возврат', 'returned'),
        ]

        StatusMapping = self.env['marketplace.status.mapping']
        count = 0

        for external_code, external_name, internal_state in rozetka_statuses:
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
                'message': _('%d status mappings created/updated for Rozetka.') % count,
                'type': 'success',
                'sticky': False,
            }
        }

    # === Order Cancellation ===
    def _api_cancel_order(self, order, reason=None, comment=None):
        """Cancel order on Rozetka."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._api_cancel_order(order, reason, comment)

        # Rozetka status 6 = Cancelled
        data = {
            'status': 6,
        }

        # Add cancellation reason if available
        if reason:
            data['cancel_reason'] = reason
        if comment:
            data['cancel_comment'] = comment

        try:
            result = self._rozetka_api_request(
                'PUT',
                f'/orders/{order.external_id}',
                data=data,
            )
            if result.get('success'):
                _logger.info(f"Order {order.name} cancelled on Rozetka")
                return True
            else:
                error = result.get('errors', {}).get('message', 'Unknown error')
                raise UserError(_('Failed to cancel order on Rozetka: %s') % error)
        except Exception as e:
            _logger.error(f"Failed to cancel order {order.name} on Rozetka: {e}")
            raise UserError(_('Failed to cancel order on Rozetka: %s') % str(e))

    # === Webhook Handling ===
    def _verify_rozetka_webhook(self, data, signature):
        """Verify Rozetka webhook signature."""
        self.ensure_one()
        if not self.webhook_secret:
            return True

        expected = hmac.new(
            self.webhook_secret.encode(),
            json.dumps(data, separators=(',', ':')).encode(),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected, signature or '')

    def _process_webhook(self, data, headers=None):
        """Process incoming Rozetka webhook."""
        self.ensure_one()
        if self.marketplace_type != 'rozetka':
            return super()._process_webhook(data, headers)

        event_type = data.get('event')

        if event_type == 'order.created':
            # Import new order
            order_data = data.get('data', {})
            if order_data:
                self._import_single_order(order_data)

        elif event_type == 'order.status_changed':
            # Update order status
            order_data = data.get('data', {})
            external_id = str(order_data.get('id'))
            order = self.env['marketplace.order'].search([
                ('backend_id', '=', self.id),
                ('external_id', '=', external_id),
            ], limit=1)
            if order:
                order._update_from_rozetka(order_data)

        return True

    def _import_single_order(self, order_data):
        """Import a single order from webhook data."""
        self.ensure_one()
        external_id = str(order_data.get('id'))

        existing = self.env['marketplace.order'].search([
            ('backend_id', '=', self.id),
            ('external_id', '=', external_id),
        ], limit=1)

        if existing:
            return existing

        order_vals = self._prepare_rozetka_order_vals(order_data)
        order = self.env['marketplace.order'].create(order_vals)
        order._create_lines_from_rozetka(order_data.get('items', []))

        if self.auto_create_sale_order:
            try:
                order.action_create_sale_order()
                if self.auto_confirm_sale_order and order.sale_order_id:
                    order.sale_order_id.action_confirm()
            except Exception as e:
                _logger.warning(f"Failed to create sale order: {e}")

        return order


class MarketplaceOrderRozetka(models.Model):
    _inherit = 'marketplace.order'

    def _update_from_rozetka(self, data):
        """Update order from Rozetka data."""
        self.ensure_one()

        status_map = {
            1: 'new',
            2: 'confirmed',
            3: 'processing',
            4: 'shipped',
            5: 'delivered',
            6: 'cancelled',
            7: 'returned',
        }

        vals = {
            'marketplace_state': str(data.get('status')),
            'state': status_map.get(data.get('status'), self.state),
        }

        delivery = data.get('delivery', {})
        if delivery.get('ttn'):
            vals['tracking_number'] = delivery['ttn']

        if data.get('is_paid'):
            vals['is_paid'] = True

        self.write(vals)

    def _create_lines_from_rozetka(self, items_data):
        """Create order lines from Rozetka items data."""
        self.ensure_one()
        Line = self.env['marketplace.order.line']

        for item in items_data:
            # Try to find product by SKU or external ID
            product = None
            sku = item.get('article') or item.get('item_id')

            if sku:
                product = self.env['product.product'].search([
                    '|',
                    ('default_code', '=', sku),
                    ('barcode', '=', sku),
                ], limit=1)

            Line.create({
                'order_id': self.id,
                'external_id': str(item.get('item_id')),
                'product_id': product.id if product else False,
                'sku': sku,
                'name': item.get('name', 'Unknown Product'),
                'quantity': float(item.get('quantity', 1)),
                'price_unit': float(item.get('price', 0)),
                'price_total': float(item.get('total', 0)),
            })


class MarketplaceOrderCancelWizardRozetka(models.TransientModel):
    """Extend cancel wizard with Rozetka-specific cancel reasons."""
    _inherit = 'marketplace.order.cancel.wizard'

    @api.model
    def _get_cancel_reasons(self):
        """Override to add Rozetka-specific cancel reasons when applicable."""
        reasons = super()._get_cancel_reasons()

        # Check if any order is from Rozetka
        order_ids = self.env.context.get('default_order_ids')
        if order_ids:
            orders = self.env['marketplace.order'].browse(
                order_ids[0][2] if isinstance(order_ids[0], (list, tuple)) else order_ids
            )
            if any(o.marketplace_type == 'rozetka' for o in orders):
                # Return Rozetka-specific reasons
                return ROZETKA_CANCEL_REASONS

        return reasons
