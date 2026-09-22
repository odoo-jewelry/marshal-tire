from odoo import models, fields


class HrOrderType(models.Model):
    _name = 'hr.order.type'
    _description = 'HR Order Type'
    _order = 'sequence, code'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    
    category = fields.Selection([
        ('hiring', 'Hiring'),
        ('transfer', 'Transfer'),
        ('termination', 'Termination'),
        ('vacation', 'Vacation'),
        ('business_trip', 'Business Trip'),
        ('bonus', 'Bonus'),
        ('disciplinary', 'Disciplinary'),
        ('other', 'Other'),
    ], string='Category', required=True, default='other')
    
    sequence_id = fields.Many2one(
        'ir.sequence',
        string='Sequence'
    )
    
    template_body = fields.Html(
        string='Template Body',
        help='HTML template for the order body'
    )
    
    requires_employee = fields.Boolean(string='Requires Employee', default=True)
    requires_contract = fields.Boolean(string='Requires Contract')
    requires_department = fields.Boolean(string='Requires Department')
    requires_date_range = fields.Boolean(string='Requires Date Range')
    
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _unique_code = models.Constraint(
        'unique(code)',
        'Order type code must be unique!',
    )
