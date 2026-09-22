from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MarketplaceOrderCancelWizard(models.TransientModel):
    _name = 'marketplace.order.cancel.wizard'
    _description = 'Marketplace Order Cancel Wizard'

    order_ids = fields.Many2many(
        'marketplace.order',
        string='Orders',
        required=True,
    )
    backend_id = fields.Many2one(
        'marketplace.backend',
        string='Backend',
        compute='_compute_backend_id',
    )
    marketplace_type = fields.Selection(
        related='backend_id.marketplace_type',
    )

    cancel_reason = fields.Selection(
        selection='_get_cancel_reasons',
        string='Cancel Reason',
        required=True,
    )
    cancel_comment = fields.Text(
        string='Comment',
        help='Additional comment about cancellation',
    )
    cancel_sale_order = fields.Boolean(
        string='Cancel Sale Order',
        default=True,
        help='Also cancel the linked Odoo Sale Order',
    )
    sync_to_marketplace = fields.Boolean(
        string='Sync to Marketplace',
        default=True,
        help='Send cancellation to marketplace API',
    )

    @api.depends('order_ids')
    def _compute_backend_id(self):
        for wizard in self:
            backends = wizard.order_ids.mapped('backend_id')
            wizard.backend_id = backends[0] if len(backends) == 1 else False

    @api.model
    def _get_cancel_reasons(self):
        """Return available cancel reasons. Override in marketplace-specific modules."""
        return [
            ('customer_request', _('Customer Request')),
            ('out_of_stock', _('Out of Stock')),
            ('pricing_error', _('Pricing Error')),
            ('duplicate_order', _('Duplicate Order')),
            ('fraud_suspicion', _('Fraud Suspicion')),
            ('delivery_issue', _('Delivery Issue')),
            ('other', _('Other')),
        ]

    def action_cancel(self):
        """Cancel orders with reason."""
        self.ensure_one()

        if not self.order_ids:
            raise UserError(_('No orders selected for cancellation.'))

        # Check all orders have same backend
        backends = self.order_ids.mapped('backend_id')
        if len(backends) > 1:
            raise UserError(_('All orders must belong to the same backend.'))

        # Check orders can be cancelled
        non_cancellable = self.order_ids.filtered(
            lambda o: o.state in ('delivered', 'cancelled', 'returned')
        )
        if non_cancellable:
            raise UserError(
                _('Cannot cancel orders that are already delivered, cancelled or returned: %s')
                % ', '.join(non_cancellable.mapped('name'))
            )

        for order in self.order_ids:
            # 1. Send cancel to marketplace API (if enabled)
            if self.sync_to_marketplace and order.backend_id:
                try:
                    order.backend_id._api_cancel_order(
                        order,
                        reason=self.cancel_reason,
                        comment=self.cancel_comment,
                    )
                except Exception as e:
                    order.message_post(
                        body=_("Failed to sync cancellation to marketplace: %s") % str(e)
                    )

            # 2. Cancel marketplace order
            order.write({
                'state': 'cancelled',
                'cancel_reason': self.cancel_reason,
                'cancel_comment': self.cancel_comment,
            })

            # 3. Cancel linked sale order if requested
            if self.cancel_sale_order and order.sale_order_id:
                if order.sale_order_id.state not in ('done', 'cancel'):
                    try:
                        order.sale_order_id._action_cancel()
                    except Exception as e:
                        order.message_post(
                            body=_("Failed to cancel sale order: %s") % str(e)
                        )

            # 4. Post to chatter
            reason_label = dict(self._get_cancel_reasons()).get(
                self.cancel_reason, self.cancel_reason
            )
            body = _("Order cancelled. Reason: %s") % reason_label
            if self.cancel_comment:
                body += _("\nComment: %s") % self.cancel_comment
            order.message_post(body=body)

        return {'type': 'ir.actions.act_window_close'}
