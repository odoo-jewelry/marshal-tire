import json
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests

from odoo import _, exceptions

_logger = logging.getLogger(__name__)

CHECKBOX_URL = 'https://api.checkbox.in.ua/api/v1/'

# TODO: Make timeout configurable. 30 sec is very small for some operations.
REQUEST_TIMEOUT = 30


class CheckboxAPI:
    """Checkbox PRRO API client."""

    def __init__(self, license_key=None, access_token=None):
        self.license_key = license_key
        self.access_token = access_token
        self.base_url = CHECKBOX_URL

    def _get_url(self, endpoint):
        return urljoin(self.base_url, endpoint.lstrip('/'))

    def _get_headers(self, with_auth=True, with_license=True):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }
        if with_auth and self.access_token:
            headers['Authorization'] = f'Bearer {self.access_token}'
        if with_license and self.license_key:
            headers['X-License-Key'] = self.license_key
        return headers

    def _request(self, method, endpoint, data=None, params=None, with_auth=True, with_license=True):
        url = self._get_url(endpoint)
        headers = self._get_headers(with_auth, with_license)

        _logger.debug('[Checkbox] %s %s', method.upper(), url)

        try:
            response = requests.request(
                method=method,
                url=url,
                data=json.dumps(data) if data else None,
                params=params,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.exceptions.Timeout:
            raise exceptions.UserError(_('Checkbox API timeout. Please try again.'))
        except requests.exceptions.ConnectionError:
            raise exceptions.UserError(_('Cannot connect to Checkbox API. Check your internet connection.'))

        if response.status_code < 200 or response.status_code >= 300:
            self._handle_error(response)

        try:
            return response.json()
        except json.JSONDecodeError:
            return response.text

    def _handle_error(self, response):
        try:
            error_data = response.json()
        except json.JSONDecodeError:
            raise exceptions.UserError(
                _('Checkbox API error (%(code)s): %(text)s',
                  code=response.status_code, text=response.text)
            )

        if error_data.get('detail'):
            if isinstance(error_data['detail'], list):
                messages = [item.get('msg', str(item)) for item in error_data['detail']]
                raise exceptions.UserError('\n'.join(messages))
            raise exceptions.UserError(str(error_data['detail']))

        if error_data.get('message'):
            raise exceptions.UserError(error_data['message'])

        raise exceptions.UserError(
            _('Checkbox API error (%(code)s): %(text)s',
              code=response.status_code, text=response.text)
        )

    def _get(self, endpoint, params=None, **kwargs):
        return self._request('GET', endpoint, params=params, **kwargs)

    def _post(self, endpoint, data=None, **kwargs):
        return self._request('POST', endpoint, data=data, **kwargs)

    # Authentication
    def cashier_signin_login_password(self, login, password):
        response = self._post(
            '/cashier/signin',
            data={'login': login, 'password': password},
            with_auth=False,
            with_license=False,
        )
        self.access_token = response.get('access_token')
        return response

    def cashier_signin_pincode(self, pin_code):
        response = self._post(
            '/cashier/signinPinCode',
            data={'pin_code': pin_code},
            with_auth=False,
            with_license=True,
        )
        self.access_token = response.get('access_token')
        return response

    def cashier_signout(self):
        return self._post('/cashier/signout')

    def cashier_me(self):
        return self._get('/cashier/me')

    # Cash Register
    def get_cash_register_info(self):
        return self._get('/cash-registers/info')

    def go_online(self):
        return self._post('/cash-registers/go-online')

    def go_offline(self):
        return self._post('/cash-registers/go-offline')

    def ping_tax_service(self):
        return self._post('/cash-registers/ping-tax-service')

    # Shifts
    def get_shift(self):
        return self._get('/cashier/shift')

    def open_shift(self):
        return self._post('/shifts')

    def close_shift(self):
        return self._post('/shifts/close')

    def get_shift_info(self, shift_id):
        return self._get(f'/shifts/{shift_id}')

    # Receipts
    def create_receipt(self, receipt_data):
        return self._post('/receipts/sell', data=receipt_data)

    def create_receipt_offline(self, receipt_data):
        return self._post('/receipts/sell-offline', data=receipt_data)

    def create_return_receipt(self, receipt_data):
        return self._post('/receipts/return', data=receipt_data)

    def get_receipt(self, receipt_id):
        return self._get(f'/receipts/{receipt_id}')

    def get_receipt_text(self, receipt_id):
        url = self._get_url(f'/receipts/{receipt_id}/text')
        response = requests.get(url, headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
        return response.content.decode('utf-8')

    def get_receipt_html(self, receipt_id):
        url = self._get_url(f'/receipts/{receipt_id}/html')
        response = requests.get(url, headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
        return response.content.decode('utf-8')

    def get_receipt_png(self, receipt_id, width=None):
        url = self._get_url(f'/receipts/{receipt_id}/png')
        params = {'width': width} if width else None
        response = requests.get(url, headers=self._get_headers(), params=params, timeout=REQUEST_TIMEOUT)
        return response.content

    def get_receipt_qrcode(self, receipt_id):
        url = self._get_url(f'/receipts/{receipt_id}/qrcode')
        response = requests.get(url, headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
        return response.content

    def search_receipts(self, params=None):
        return self._get('/receipts/search', params=params)

    # Service receipts (cash in/out)
    def create_service_receipt(self, receipt_data):
        return self._post('/receipts/service', data=receipt_data)

    # Reports
    def create_x_report(self):
        return self._post('/reports')

    def get_report(self, report_id):
        return self._get(f'/reports/{report_id}')

    def get_report_text(self, report_id):
        url = self._get_url(f'/reports/{report_id}/text')
        response = requests.get(url, headers=self._get_headers(), timeout=REQUEST_TIMEOUT)
        return response.content.decode('utf-8')

    # Taxes
    def get_taxes(self):
        return self._get('/tax')

    # Offline codes
    def ask_offline_codes(self, count=None):
        params = {'count': count} if count else None
        return self._get('/cash-registers/ask-offline-codes', params=params)

    def get_offline_codes(self):
        return self._get('/cash-registers/get-offline-codes')

    def get_offline_time(self):
        return self._get('/cash-registers/get-offline-time')


def parse_checkbox_datetime(date_str):
    """Parse datetime string from Checkbox API response."""
    patterns = [
        '%Y-%m-%dT%H:%M:%S.%f+00:00',
        '%Y-%m-%dT%H:%M:%S+00:00',
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
    ]
    for pattern in patterns:
        try:
            return datetime.strptime(date_str, pattern)
        except (ValueError, TypeError):
            continue
    return None
