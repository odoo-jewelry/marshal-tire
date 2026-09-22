import logging
import traceback

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MonobankAcquiringWebhook(http.Controller):

    @http.route(
        '/l10n_ua_mono_acquiring/webhook',
        methods=['POST'],
        type='http',
        csrf=False,
        auth='public',
    )
    def mono_webhook(self):
        try:
            data = request.get_json_data()
            _logger.info("Monobank acquiring webhook: %s", data)

            invoice_id = data.get('invoiceId')
            reference = data.get('reference')
            status = data.get('status')

            if not invoice_id or status != 'success':
                return request.make_response(
                    'ok', [('Content-Type', 'text/plain')])

            # Try sale.order first, then account.move
            order = request.env['sale.order'].sudo().search(
                [('mono_invoice_id', '=', invoice_id)], limit=1)
            if order:
                self._process_sale_order(order, data)
            else:
                move = request.env['account.move'].sudo().search(
                    [('mono_invoice_id', '=', invoice_id)], limit=1)
                if move:
                    self._process_invoice(move, data)
                else:
                    _logger.warning(
                        "Monobank webhook: no order/invoice for "
                        "invoiceId=%s ref=%s", invoice_id, reference)

        except Exception:
            _logger.error("Monobank webhook error:\n%s", traceback.format_exc())

        return request.make_response('ok', [('Content-Type', 'text/plain')])

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _process_sale_order(self, order, data):
        """Confirm order, create invoice, register payment."""
        _logger.info("Monobank webhook: processing sale.order %s", order.name)

        if order.state != 'sale':
            order.action_confirm()

        if order.invoice_status == 'to invoice':
            invoices = order._create_invoices()
            invoices.action_post()
        else:
            invoices = order.invoice_ids.filtered(
                lambda m: m.state == 'posted' and m.payment_state != 'paid')

        if invoices:
            request.env['account.payment.register'].sudo().with_context(
                active_ids=invoices.ids,
                active_model='account.move',
            ).create({})._create_payments()
        else:
            _logger.warning(
                "Monobank webhook: no invoices to pay for %s", order.name)

    def _process_invoice(self, move, data):
        """Register payment for existing posted invoice."""
        _logger.info("Monobank webhook: processing account.move %s", move.name)

        if move.state != 'posted':
            _logger.warning("Monobank webhook: invoice %s not posted", move.name)
            return

        if move.payment_state == 'paid':
            _logger.info(
                "Monobank webhook: invoice %s already paid", move.name)
            return

        request.env['account.payment.register'].sudo().with_context(
            active_ids=[move.id],
            active_model='account.move',
        ).create({})._create_payments()
