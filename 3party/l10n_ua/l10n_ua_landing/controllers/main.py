from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website


class WebsiteLanding(Website):
    """Віддаємо власний лендинг на / замість дефолтної сторінки Odoo Website.

    Виняток — коли головну вантажить редактор/білдер сайту в <iframe>
    (Sec-Fetch-Dest: iframe): тоді повертаємо звичайну домашню сторінку
    Odoo, інакше білдер падає (contentDocument без нашого raw-документа).
    """

    @http.route()
    def index(self, **kw):
        if request.httprequest.headers.get('Sec-Fetch-Dest') == 'iframe':
            return super().index(**kw)
        html = request.env['ir.qweb']._render('l10n_ua_landing.landing_page')
        return request.make_response(
            '<!DOCTYPE html>\n' + str(html),
            headers=[('Content-Type', 'text/html; charset=utf-8')],
        )
