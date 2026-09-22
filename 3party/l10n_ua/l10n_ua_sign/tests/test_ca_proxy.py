"""Тести проксі до ЦСК для браузерної бібліотеки підпису (/l10n_ua_sign/ca_proxy).

Проксі не має ставати відкритим релеєм (SSRF): пускає лише користувачів Odoo
і лише до хостів зі списку ЦСК. Сам CAs.json у git не лежить, тож перелік
хостів у тестах підміняємо.
"""

import base64
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

from odoo.tests import HttpCase, tagged

from odoo.addons.l10n_ua_sign.controllers.ca_proxy import _split_address

MODULE = 'odoo.addons.l10n_ua_sign.controllers.ca_proxy'
PROXY = '/l10n_ua_sign/ca_proxy'


@tagged('post_install', '-at_install')
class TestKepCaProxy(HttpCase):

    def setUp(self):
        super().setUp()
        hosts = patch(MODULE + '._allowed_hosts', return_value=frozenset({'ca.tax.gov.ua'}))
        hosts.start()
        self.addCleanup(hosts.stop)
        upstream = patch(MODULE + '.requests.request')
        self.upstream = upstream.start()
        self.addCleanup(upstream.stop)

    def _post(self, address, body=b'REQ', content_type='application/ocsp-request'):
        query = urlencode({'address': address, 'contentType': content_type})
        return self.url_open(
            f'{PROXY}?{query}', data=base64.b64encode(body),
            headers={'Content-Type': 'X-user/base64-data'}, allow_redirects=False)

    def _upstream_returns(self, status, content):
        response = MagicMock(status_code=status)
        response.raw.read.return_value = content
        self.upstream.return_value = response

    def test_requires_login(self):
        res = self._post('ca.tax.gov.ua/services/ocsp/')
        self.assertNotEqual(res.status_code, 200)
        self.upstream.assert_not_called()

    def test_forwards_to_allowed_ca(self):
        self.authenticate('admin', 'admin')
        self._upstream_returns(200, b'OCSP-RESPONSE')
        res = self._post('ca.tax.gov.ua/services/ocsp/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(base64.b64decode(res.content), b'OCSP-RESPONSE')
        args, kwargs = self.upstream.call_args
        self.assertEqual(args, ('POST', 'http://ca.tax.gov.ua/services/ocsp/'))
        self.assertEqual(kwargs['data'], b'REQ')
        self.assertEqual(kwargs['headers'], {'Content-Type': 'application/ocsp-request'})
        self.assertFalse(kwargs['allow_redirects'])

    def test_rejects_host_outside_ca_list(self):
        self.authenticate('admin', 'admin')
        for address in ('localhost:8069/web', '169.254.169.254/latest/meta-data',
                        'ca.tax.gov.ua.evil.example/x', 'file:///etc/passwd'):
            with self.subTest(address=address):
                self.assertEqual(self._post(address).status_code, 403)
        self.upstream.assert_not_called()

    def test_rejects_credentials_in_address(self):
        self.authenticate('admin', 'admin')
        self.assertEqual(self._post('user:pw@ca.tax.gov.ua/x').status_code, 403)
        self.upstream.assert_not_called()

    def test_upstream_error_is_not_relayed(self):
        self.authenticate('admin', 'admin')
        self._upstream_returns(500, b'internal details')
        res = self._post('ca.tax.gov.ua/services/cmp/')
        self.assertEqual(res.status_code, 502)
        self.assertNotIn(b'internal details', res.content)

    def test_split_address(self):
        self.assertEqual(_split_address('CA.tax.gov.ua:80/services/tsp/'),
                         ('ca.tax.gov.ua', 'http://CA.tax.gov.ua:80/services/tsp/'))
        self.assertEqual(_split_address('https://ca.tax.gov.ua/x')[0], 'ca.tax.gov.ua')
        self.assertEqual(_split_address('ftp://ca.tax.gov.ua/x'), ('', ''))
        self.assertEqual(_split_address('ca.tax.gov.ua:notaport/x'), ('', ''))
        self.assertEqual(_split_address(''), ('', ''))
