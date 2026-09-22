from odoo import models, fields, api
from odoo.exceptions import ValidationError


class HrExecutionDocument(models.Model):
    _name = 'hr.execution.document'
    _description = 'Execution Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc'

    name = fields.Char(
        string='Document Number',
        required=True,
        tracking=True
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True
    )
    
    document_type = fields.Selection([
        ('alimony', 'Alimony'),
        ('court_decision', 'Court Decision'),
        ('tax_debt', 'Tax Debt'),
        ('other_debt', 'Other Debt'),
    ], string='Document Type', required=True, default='alimony', tracking=True)
    
    recipient_name = fields.Char(string='Recipient Name', required=True)
    recipient_rnokpp = fields.Char(string='Recipient RNOKPP')
    recipient_account = fields.Char(string='Recipient Account (IBAN)')
    recipient_bank = fields.Char(string='Recipient Bank')
    
    calculation_method = fields.Selection([
        ('percent', 'Percent of Income'),
        ('fixed', 'Fixed Amount'),
        ('percent_min_wage', 'Percent of Minimum Wage'),
    ], string='Calculation Method', required=True, default='percent')
    
    percent_value = fields.Float(string='Percent (%)')
    fixed_amount = fields.Float(string='Fixed Amount')
    
    deduction_priority = fields.Selection([
        ('1', 'First Priority (Alimony for minors)'),
        ('2', 'Second Priority (Other alimony)'),
        ('3', 'Third Priority (Other debts)'),
    ], string='Deduction Priority', default='1')
    
    max_deduction_percent = fields.Float(
        string='Max Deduction (%)',
        default=50.0,
        help='Maximum percent of salary that can be deducted (50% or 70% for alimony)'
    )
    
    date_from = fields.Date(string='Date From', required=True, tracking=True)
    date_to = fields.Date(string='Date To', tracking=True)
    
    total_amount = fields.Float(string='Total Amount to Collect')
    payslip_deduction_ids = fields.One2many(
        'hr.payslip.deduction',
        'execution_doc_id',
        string='Payslip Deductions',
    )
    collected_amount = fields.Float(
        string='Collected Amount',
        compute='_compute_collected_amount',
        store=True
    )
    remaining_amount = fields.Float(
        string='Remaining Amount',
        compute='_compute_collected_amount',
        store=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('suspended', 'Suspended'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True)
    
    notes = fields.Text(string='Notes')
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.employee_id and self.employee_id.company_id \
                and self.employee_id.company_id != self.company_id:
            self.employee_id = False

    @api.depends('total_amount',
                 'payslip_deduction_ids.amount',
                 'payslip_deduction_ids.payslip_id.state')
    def _compute_collected_amount(self):
        for doc in self:
            # Only confirmed (posted) payslips count as actually collected.
            doc.collected_amount = sum(
                d.amount for d in doc.payslip_deduction_ids
                if d.payslip_id.state == 'done'
            )
            doc.remaining_amount = doc.total_amount - doc.collected_amount

    @api.constrains('percent_value')
    def _check_percent(self):
        for doc in self:
            if doc.calculation_method == 'percent' and (doc.percent_value <= 0 or doc.percent_value > 70):
                raise ValidationError('Percent must be between 0 and 70.')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for doc in self:
            if doc.date_to and doc.date_from > doc.date_to:
                raise ValidationError('Start date must be before end date.')

    def action_activate(self):
        self.write({'state': 'active'})

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_close(self):
        self.write({'state': 'closed'})

    def action_draft(self):
        self.write({'state': 'draft'})
