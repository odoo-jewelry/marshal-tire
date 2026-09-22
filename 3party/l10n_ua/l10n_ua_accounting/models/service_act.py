"""Ukrainian Service Act (Акт наданих послуг) model."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ServiceAct(models.Model):
    """Service Act (Акт наданих послуг / Акт виконаних робіт).

    A document that confirms the provision of services or completion of work.
    It serves as the basis for recognizing revenue and issuing an invoice.
    """
    _name = 'l10n_ua.service.act'
    _description = 'Service Act'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Number',
        required=True,
        copy=False,
        readonly=True,
        default='/',
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        domain="['|', ('parent_id', '=', False), ('is_company', '=', True)]",
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    # Contract reference
    contract_number = fields.Char(
        string='Contract Number',
        help='Reference to the contract under which services are provided',
    )
    contract_date = fields.Date(
        string='Contract Date',
    )

    # Period of service
    period_from = fields.Date(
        string='Period From',
        help='Start date of service period',
    )
    period_to = fields.Date(
        string='Period To',
        help='End date of service period',
    )

    # Lines
    line_ids = fields.One2many(
        'l10n_ua.service.act.line',
        'act_id',
        string='Lines',
    )

    # Amounts
    amount_untaxed = fields.Monetary(
        string='Untaxed Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_tax = fields.Monetary(
        string='Tax Amount',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    amount_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    # State
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('invoiced', 'Invoiced'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    # Related invoice
    invoice_id = fields.Many2one(
        'account.move',
        string='Invoice',
        readonly=True,
        copy=False,
    )

    # Notes
    note = fields.Text(string='Notes')

    @api.depends('line_ids.price_subtotal', 'line_ids.price_tax')
    def _compute_amounts(self):
        for act in self:
            act.amount_untaxed = sum(act.line_ids.mapped('price_subtotal'))
            act.amount_tax = sum(act.line_ids.mapped('price_tax'))
            act.amount_total = act.amount_untaxed + act.amount_tax

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'l10n_ua.service.act'
                ) or '/'
        return super().create(vals_list)

    def action_confirm(self):
        """Confirm the service act."""
        for act in self:
            if act.state != 'draft':
                raise UserError(_('Only draft acts can be confirmed.'))
            if not act.line_ids:
                raise UserError(_('Cannot confirm an act without lines.'))
            act.state = 'confirmed'

    def action_draft(self):
        """Reset to draft state."""
        for act in self:
            if act.state == 'invoiced':
                raise UserError(_('Cannot reset an invoiced act to draft.'))
            act.state = 'draft'

    def action_cancel(self):
        """Cancel the service act."""
        for act in self:
            if act.state == 'invoiced':
                raise UserError(_('Cannot cancel an invoiced act.'))
            act.state = 'cancelled'

    def action_create_invoice(self):
        """Create an invoice from this service act."""
        self.ensure_one()

        if self.state != 'confirmed':
            raise UserError(_('Only confirmed acts can be invoiced.'))

        if self.invoice_id:
            raise UserError(_('Invoice already exists for this act.'))

        invoice_lines = []
        for line in self.line_ids:
            invoice_lines.append((0, 0, {
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
                'tax_ids': [(6, 0, line.tax_ids.ids)],
                'product_id': line.product_id.id if line.product_id else False,
            }))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'currency_id': self.currency_id.id,
            'invoice_line_ids': invoice_lines,
            'ref': _('Service Act %s') % self.name,
        })

        self.invoice_id = invoice
        self.state = 'invoiced'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoice(self):
        """View the related invoice."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_('No invoice exists for this act.'))
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_print(self):
        """Print the service act."""
        self.ensure_one()
        return self.env.ref(
            'l10n_ua_accounting.action_report_service_act'
        ).report_action(self)


class ServiceActLine(models.Model):
    """Service Act Line."""
    _name = 'l10n_ua.service.act.line'
    _description = 'Service Act Line'
    _order = 'sequence, id'

    act_id = fields.Many2one(
        'l10n_ua.service.act',
        string='Service Act',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='Sequence', default=10)

    product_id = fields.Many2one(
        'product.product',
        string='Service',
        domain="[('type', '=', 'service')]",
    )
    name = fields.Text(
        string='Description',
        required=True,
    )
    quantity = fields.Float(
        string='Quantity',
        required=True,
        default=1.0,
    )
    uom_id = fields.Many2one(
        'uom.uom',
        string='Unit of Measure',
    )
    price_unit = fields.Float(
        string='Unit Price',
        required=True,
    )
    tax_ids = fields.Many2many(
        'account.tax',
        string='Taxes',
        domain="[('type_tax_use', '=', 'sale')]",
    )

    # Computed amounts
    price_subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    price_tax = fields.Monetary(
        string='Tax',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    price_total = fields.Monetary(
        string='Total',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )

    currency_id = fields.Many2one(
        related='act_id.currency_id',
        string='Currency',
    )

    @api.depends('quantity', 'price_unit', 'tax_ids')
    def _compute_amounts(self):
        for line in self:
            subtotal = line.quantity * line.price_unit
            taxes = line.tax_ids.compute_all(
                subtotal,
                currency=line.currency_id,
                quantity=1.0,
            )
            line.price_subtotal = taxes['total_excluded']
            line.price_tax = taxes['total_included'] - taxes['total_excluded']
            line.price_total = taxes['total_included']

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.price_unit = self.product_id.lst_price
            self.uom_id = self.product_id.uom_id
            if self.product_id.taxes_id:
                self.tax_ids = self.product_id.taxes_id.filtered(
                    lambda t: t.company_id == self.act_id.company_id
                )
