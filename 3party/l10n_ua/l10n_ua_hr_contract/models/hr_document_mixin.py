from odoo import models, fields, api


class HrDocumentMixin(models.AbstractModel):
    """Abstract mixin for HR document-like models with common fields.

    Provides:
    - Reference number (name) with sequence
    - Display name computation
    - Order number and date (required)
    - State management
    - Common tracking
    """
    _name = 'hr.document.mixin'
    _description = 'HR Document Mixin'

    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
        tracking=True
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    # Order references (will be linked to hr.order by l10n_ua_hr_documents)
    order_number = fields.Char(
        string='Order Number',
        required=True,
        tracking=True
    )
    order_date = fields.Date(
        string='Order Date',
        required=True,
        tracking=True
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    def _get_sequence_code(self):
        """Override in child models to provide sequence code"""
        return False

    def _get_display_name_parts(self):
        """Override in child models to provide display name parts.

        Returns:
            tuple: (main_part, order_number)
        """
        return ('Document', self.order_number or 'New')

    @api.depends('order_number')
    def _compute_display_name(self):
        for record in self:
            main_part, order_part = record._get_display_name_parts()
            record.display_name = f"{main_part} ({order_part})"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                sequence_code = self._get_sequence_code()
                if sequence_code:
                    vals['name'] = self.env['ir.sequence'].next_by_code(sequence_code) or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        """Confirm the document"""
        self.write({'state': 'confirmed'})

    def action_cancel(self):
        """Cancel the document"""
        self.write({'state': 'cancelled'})

    def action_draft(self):
        """Reset to draft"""
        self.write({'state': 'draft'})
