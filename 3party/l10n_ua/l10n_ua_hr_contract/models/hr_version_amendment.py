from odoo import models, fields, api
from odoo.exceptions import UserError


class HrVersionAmendment(models.Model):
    _name = 'hr.version.amendment'
    _description = 'Version Amendment'
    _order = 'amendment_date desc, id desc'
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

    amendment_number = fields.Char(
        string='Amendment Number',
        tracking=True
    )
    amendment_date = fields.Date(
        string='Amendment Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        tracking=True
    )

    amendment_type = fields.Selection([
        ('salary', 'Salary Change'),
        ('position', 'Position Change'),
        ('schedule', 'Schedule Change'),
        ('conditions', 'Work Conditions Change'),
        ('extension', 'Contract Extension'),
        ('other', 'Other'),
    ], string='Amendment Type', required=True, tracking=True)

    description = fields.Text(
        string='Description',
        required=True,
        help='Detailed description of changes made'
    )

    old_values = fields.Text(
        string='Previous Values',
        help='Previous field values before amendment'
    )
    new_values = fields.Text(
        string='New Values',
        help='New field values after amendment'
    )

    order_number = fields.Char(string='Order Number', required=True, tracking=True)
    order_date = fields.Date(string='Order Date', required=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    @api.depends('employee_id', 'amendment_type', 'order_number')
    def _compute_display_name(self):
        type_names = dict(self._fields['amendment_type'].selection)
        for record in self:
            if record.employee_id and record.amendment_type:
                type_label = type_names.get(record.amendment_type, record.amendment_type)
                record.display_name = f"{record.employee_id.name} - {type_label} ({record.order_number or 'New'})"
            else:
                record.display_name = record.name or 'New'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.version.amendment') or 'New'
        return super().create(vals_list)

    def action_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError('Only draft amendments can be confirmed.')
            record.state = 'confirmed'

    def action_draft(self):
        for record in self:
            record.state = 'draft'

    @api.model
    def create_from_change(self, version, amendment_type, description, old_vals, new_vals):
        import json
        return self.create({
            'version_id': version.id,
            'amendment_type': amendment_type,
            'description': description,
            'effective_date': fields.Date.today(),
            'old_values': json.dumps(old_vals, default=str, ensure_ascii=False),
            'new_values': json.dumps(new_vals, default=str, ensure_ascii=False),
        })
