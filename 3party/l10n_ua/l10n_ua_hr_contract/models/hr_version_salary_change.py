from odoo import models, fields, api
from odoo.exceptions import UserError


class HrVersionSalaryChange(models.Model):
    _name = 'hr.version.salary.change'
    _description = 'Version Salary Change'
    _order = 'effective_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    name = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New'
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    version_id = fields.Many2one(
        'hr.version',
        string='Employee Version',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        related='version_id.employee_id',
        store=True
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='version_id.company_id',
        store=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='version_id.currency_id'
    )

    old_wage = fields.Monetary(
        string='Previous Salary',
        required=True,
        currency_field='currency_id'
    )
    new_wage = fields.Monetary(
        string='New Salary',
        required=True,
        currency_field='currency_id'
    )
    change_amount = fields.Monetary(
        string='Change Amount',
        compute='_compute_change_amount',
        store=True,
        currency_field='currency_id'
    )
    change_percent = fields.Float(
        string='Change %',
        compute='_compute_change_amount',
        store=True
    )

    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        tracking=True
    )
    reason = fields.Text(string='Reason for Change')

    order_number = fields.Char(string='Order Number', required=True, tracking=True)
    order_date = fields.Date(string='Order Date', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('applied', 'Applied'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    @api.depends('employee_id', 'effective_date', 'order_number')
    def _compute_display_name(self):
        for record in self:
            if record.employee_id and record.effective_date:
                record.display_name = f"{record.employee_id.name} - {record.effective_date} ({record.order_number or 'New'})"
            else:
                record.display_name = record.name or 'New'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.version.salary.change') or 'New'
        return super().create(vals_list)

    @api.depends('old_wage', 'new_wage')
    def _compute_change_amount(self):
        for record in self:
            record.change_amount = record.new_wage - record.old_wage
            if record.old_wage:
                record.change_percent = ((record.new_wage - record.old_wage) / record.old_wage) * 100
            else:
                record.change_percent = 0

    @api.onchange('version_id')
    def _onchange_version_id(self):
        if self.version_id:
            self.old_wage = self.version_id.wage

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError('Only draft salary changes can be confirmed.')
            record.state = 'confirmed'

    def action_apply(self):
        for record in self:
            if record.state != 'confirmed':
                raise UserError('Only confirmed salary changes can be applied.')
            if record.effective_date > fields.Date.today():
                raise UserError('Cannot apply salary change before its effective date.')
            record.version_id.wage = record.new_wage
            record.state = 'applied'

    def action_cancel(self):
        for record in self:
            if record.state == 'applied':
                raise UserError('Cannot cancel an already applied salary change.')
            record.state = 'cancelled'

    def action_draft(self):
        for record in self:
            if record.state == 'applied':
                raise UserError('Cannot reset an applied salary change to draft.')
            record.state = 'draft'
