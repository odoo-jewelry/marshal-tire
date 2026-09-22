from odoo import api, fields, models


class L10nUaPrroReceipt(models.Model):
    _name = 'l10n_ua.prro.receipt'
    _description = 'PRRO Fiscal Receipt'
    _order = 'create_date desc'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    fiscal_number = fields.Char(
        string='Fiscal Number',
        index=True,
    )
    local_number = fields.Integer(
        string='Local Number',
    )
    shift_id = fields.Many2one(
        'l10n_ua.prro.shift',
        string='Shift',
        required=True,
    )
    config_id = fields.Many2one(
        'l10n_ua.prro.config',
        related='shift_id.config_id',
        store=True,
    )
    receipt_type = fields.Selection(
        selection=[
            ('sale', 'Sale'),
            ('return', 'Return'),
            ('service_input', 'Service Input'),
            ('service_output', 'Service Output'),
        ],
        string='Receipt Type',
        required=True,
        default='sale',
    )
    payment_type = fields.Selection(
        selection=[
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('mixed', 'Mixed'),
        ],
        string='Payment Type',
        default='cash',
    )
    cash_amount = fields.Monetary(
        string='Cash Amount',
        currency_field='currency_id',
    )
    card_amount = fields.Monetary(
        string='Card Amount',
        currency_field='currency_id',
    )
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total',
        store=True,
        currency_field='currency_id',
    )
    tax_amount = fields.Monetary(
        string='Tax Amount',
        currency_field='currency_id',
    )
    line_ids = fields.One2many(
        'l10n_ua.prro.receipt.line',
        'receipt_id',
        string='Lines',
    )
    pos_order_id = fields.Many2one(
        'pos.order',
        string='POS Order',
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('registered', 'Registered'),
            ('error', 'Error'),
        ],
        string='State',
        default='draft',
    )
    error_message = fields.Text(
        string='Error Message',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='config_id.company_id.currency_id',
    )
    qr_code = fields.Char(
        string='QR Code URL',
    )

    @api.depends('fiscal_number', 'local_number')
    def _compute_name(self):
        for receipt in self:
            if receipt.fiscal_number:
                receipt.name = f'Receipt #{receipt.fiscal_number}'
            else:
                receipt.name = f'Receipt (local #{receipt.local_number})'

    @api.depends('cash_amount', 'card_amount', 'line_ids.subtotal')
    def _compute_total(self):
        for receipt in self:
            payment_total = receipt.cash_amount + receipt.card_amount
            # Fall back to the goods subtotal when the payment split is not set
            # (e.g. receipt built from lines), so the total is never a bogus 0.
            receipt.total_amount = payment_total or sum(
                receipt.line_ids.mapped('subtotal')
            )

    @api.model
    def _prepare_payment_vals(self, payments):
        """Map a Checkbox payments list to cash/card/payment_type values.

        Checkbox monetary values are in kopecks; ``type`` is ``CASH`` or
        ``CASHLESS`` (card). Returns a vals dict so the stored ``total_amount``
        compute (cash + card) yields the real receipt total.
        """
        cash = card = 0.0
        for payment in payments or []:
            value = (payment.get('value') or 0) / 100.0
            if (payment.get('type') or '').upper() == 'CASH':
                cash += value
            else:
                card += value
        if cash and card:
            payment_type = 'mixed'
        elif card:
            payment_type = 'card'
        else:
            payment_type = 'cash'
        return {
            'cash_amount': cash,
            'card_amount': card,
            'payment_type': payment_type,
        }


class L10nUaPrroReceiptLine(models.Model):
    _name = 'l10n_ua.prro.receipt.line'
    _description = 'PRRO Receipt Line'
    _order = 'sequence, id'

    receipt_id = fields.Many2one(
        'l10n_ua.prro.receipt',
        string='Receipt',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
    )
    name = fields.Char(
        string='Description',
        required=True,
    )
    uktzed_code = fields.Char(
        string='UKTZED Code',
    )
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
    )
    price_unit = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
    )
    discount = fields.Float(
        string='Discount (%)',
    )
    tax_rate = fields.Float(
        string='Tax Rate (%)',
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='receipt_id.currency_id',
    )

    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Take the description and the УКТ ЗЕД code from the product.

        The code is mandatory in a receipt for excisable and for imported
        goods, and it belongs to the product — typing it per line, as this
        model used to require, is how a receipt ends up without one.
        Only an empty field is filled: a line edited by hand keeps its value.
        """
        for line in self:
            if not line.product_id:
                continue
            if not line.name:
                line.name = line.product_id.display_name
            if not line.uktzed_code:
                line.uktzed_code = line.product_id.uktzed_code

    @api.depends('quantity', 'price_unit', 'discount')
    def _compute_subtotal(self):
        for line in self:
            subtotal = line.quantity * line.price_unit
            if line.discount:
                subtotal *= (1 - line.discount / 100)
            line.subtotal = subtotal
