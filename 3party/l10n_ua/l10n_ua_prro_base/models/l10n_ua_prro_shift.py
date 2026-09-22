from odoo import api, fields, models


class L10nUaPrroShift(models.Model):
    _name = 'l10n_ua.prro.shift'
    _description = 'PRRO Shift'
    _order = 'open_date desc'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    config_id = fields.Many2one(
        'l10n_ua.prro.config',
        string='PRRO Configuration',
        required=True,
    )
    shift_number = fields.Integer(
        string='Shift Number',
    )
    open_date = fields.Datetime(
        string='Open Date',
        default=fields.Datetime.now,
    )
    close_date = fields.Datetime(
        string='Close Date',
    )
    cashier_id = fields.Many2one(
        'res.users',
        string='Cashier',
        default=lambda self: self.env.user,
    )
    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string='State',
        default='open',
    )
    receipt_ids = fields.One2many(
        'l10n_ua.prro.receipt',
        'shift_id',
        string='Receipts',
    )
    receipt_count = fields.Integer(
        string='Receipt Count',
        compute='_compute_totals',
        store=True,
    )
    total_sales = fields.Monetary(
        string='Total Sales',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_returns = fields.Monetary(
        string='Total Returns',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_cash = fields.Monetary(
        string='Total Cash',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_card = fields.Monetary(
        string='Total Card',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    service_input = fields.Monetary(
        string='Service Input',
        currency_field='currency_id',
    )
    service_output = fields.Monetary(
        string='Service Output',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='config_id.company_id.currency_id',
    )
    z_report_number = fields.Char(
        string='Z-Report Number',
    )

    @api.depends('config_id', 'shift_number', 'open_date')
    def _compute_name(self):
        for shift in self:
            date_str = shift.open_date.strftime('%d.%m.%Y') if shift.open_date else ''
            shift.name = f'Shift #{shift.shift_number} ({date_str})'

    @api.depends('receipt_ids.total_amount', 'receipt_ids.receipt_type', 'receipt_ids.payment_type')
    def _compute_totals(self):
        for shift in self:
            receipts = shift.receipt_ids
            shift.receipt_count = len(receipts)
            shift.total_sales = sum(r.total_amount for r in receipts if r.receipt_type == 'sale')
            shift.total_returns = sum(r.total_amount for r in receipts if r.receipt_type == 'return')
            shift.total_cash = sum(r.total_amount for r in receipts if r.payment_type == 'cash')
            shift.total_card = sum(r.total_amount for r in receipts if r.payment_type == 'card')

    def action_close(self):
        self.write({
            'state': 'closed',
            'close_date': fields.Datetime.now(),
        })
