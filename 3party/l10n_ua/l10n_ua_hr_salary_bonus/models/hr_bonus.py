from odoo import models, fields, api, _
from odoo.exceptions import UserError


class HrBonus(models.Model):
    _name = 'hr.bonus'
    _description = 'Employee Bonus'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        index=True,
    )
    bonus_type_id = fields.Many2one(
        'hr.bonus.type',
        string='Bonus Type',
        required=True,
        tracking=True,
    )
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
    ], string='Status',
        default='draft',
        required=True,
        tracking=True,
        index=True,
    )
    notes = fields.Text(
        string='Notes',
    )
    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        readonly=True,
        copy=False,
        help='Payslip that includes this bonus',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.bonus') or _('New')
        return super().create(vals_list)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.employee_id and self.employee_id.company_id \
                and self.employee_id.company_id != self.company_id:
            self.employee_id = False

    def action_confirm(self):
        """Confirm the bonus - makes it ready for payroll inclusion."""
        for bonus in self:
            if bonus.state != 'draft':
                raise UserError(_('Only draft bonuses can be confirmed.'))
            if not bonus.employee_id.bonus_system_enabled:
                raise UserError(_(
                    'Bonus system is not enabled for employee %s. '
                    'Enable it in employee settings first.'
                ) % bonus.employee_id.name)
        self.write({'state': 'confirmed'})

    def action_draft(self):
        """Reset bonus to draft state."""
        for bonus in self:
            if bonus.state == 'paid':
                raise UserError(_('Paid bonuses cannot be reset to draft.'))
        self.write({'state': 'draft', 'payslip_id': False})

    def action_cancel(self):
        """Cancel the bonus (back to draft)."""
        self.action_draft()

    def unlink(self):
        for bonus in self:
            if bonus.state == 'paid':
                raise UserError(_('Cannot delete paid bonuses.'))
        return super().unlink()
