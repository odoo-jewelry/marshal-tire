"""HTTP-проксі до ЦСК для браузерної бібліотеки підпису IIT (EndUser).

Бібліотека в режимі JS не може звертатися до серверів ЦСК (CMP, OCSP, TSP)
напряму через CORS і шле запити сюди:

    POST /l10n_ua_sign/ca_proxy?address=<хост[:порт]/шлях>&contentType=<тип>
    Content-Type: X-user/base64-data

    <base64 тіла запиту>

а у відповідь чекає base64 тіла відповіді ЦСК. Ключ і пароль сюди не
потрапляють: через проксі йдуть лише запити сертифікатів і статусів.

Щоб маршрут не став відкритим проксі (SSRF), адреса пропускається лише до
хостів із переліку ЦСК (data/CAs.json), лише http/https, без редиректів і з
обмеженням розміру.
"""
import base64
import binascii
import functools
import json
import logging
import os
from urllib.parse import urlsplit

import requests

from odoo import http
from odoo.http import request, Response
from odoo.tools import file_path

_logger = logging.getLogger(__name__)

CAS_JSON = 'l10n_ua_sign/static/src/lib/euscp/data/CAs.json'
CA_ADDRESS_KEYS = ('address', 'cmpAddress', 'tspAddress', 'ocspAccessPointAddress')
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
# (з'єднання, читання). У режимі «визначати автоматично» бібліотека питає ЦСК
# по черзі, і один недоступний ЦСК із таймаутом 30 с затримував зчитування
# ключа на пів хвилини; живі ЦСК з'єднуються за мілісекунди.
TIMEOUT = (5, 20)


def _split_address(address):
    """Хост і повний URL з адреси бібліотеки: 'ca.tax.gov.ua/services/ocsp/'.

    Порожній хост означає, що адреса непридатна (інша схема, логін у URL).
    """
    address = (address or '').strip()
    if not address:
        return '', ''
    url = address if '://' in address else f'http://{address}'
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 — кидає ValueError на некоректний порт
    except ValueError:
        return '', ''
    if parts.scheme not in ('http', 'https') or parts.username or parts.password:
        return '', ''
    return (parts.hostname or '').lower(), url


@functools.lru_cache(maxsize=4)
def _hosts_from_file(path, mtime):
    with open(path, encoding='utf-8-sig') as f:
        cas = json.load(f)
    return frozenset(
        host
        for ca in cas
        for key in CA_ADDRESS_KEYS
        for host in [_split_address(ca.get(key))[0]]
        if host
    )


def _allowed_hosts():
    """Хости ЦСК зі списку бібліотеки; перечитується, коли файл оновили."""
    try:
        path = file_path(CAS_JSON)
    except FileNotFoundError:
        return frozenset()
    return _hosts_from_file(path, os.path.getmtime(path))


class KepCaProxy(http.Controller):

    @http.route('/l10n_ua_sign/ca_proxy', type='http', auth='user',
                methods=['GET', 'POST'], csrf=False)
    def ca_proxy(self, address='', contentType='', **kwargs):
        host, url = _split_address(address)
        if not host or host not in _allowed_hosts():
            _logger.warning("КЕП-проксі: відхилено адресу %r", address)
            return Response('Address not allowed', status=403)

        method = request.httprequest.method
        body = None
        if method == 'POST':
            raw = request.httprequest.get_data(cache=False)
            try:
                body = base64.b64decode(raw)
            except (binascii.Error, ValueError):
                return Response('Bad request body', status=400)
            if len(body) > MAX_REQUEST_BYTES:
                return Response('Request too large', status=413)

        headers = {'Content-Type': contentType} if contentType else {}
        try:
            upstream = requests.request(
                method, url, data=body, headers=headers, timeout=TIMEOUT,
                allow_redirects=False, stream=True)
            content = upstream.raw.read(MAX_RESPONSE_BYTES + 1, decode_content=True)
        except requests.RequestException as e:
            _logger.warning("КЕП-проксі: ЦСК %s недоступний: %s", host, e)
            return Response('CA unavailable', status=502)

        if upstream.status_code != 200 or len(content) > MAX_RESPONSE_BYTES:
            _logger.warning("КЕП-проксі: ЦСК %s відповів %s", host, upstream.status_code)
            return Response('CA error', status=502)
        return Response(base64.b64encode(content), status=200,
                        content_type='X-user/base64-data')
