from odoo import models, fields


class HrPayslipDeduction(models.Model):
    _name = 'hr.payslip.deduction'
    _description = 'Payslip Deduction'
    _order = 'priority, sequence, id'

    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        required=True,
        ondelete='cascade'
    )
    deduction_type_id = fields.Many2one(
        'hr.deduction.type',
        string='Deduction Type',
        required=True
    )
    sequence = fields.Integer(
        string='Sequence',
        related='deduction_type_id.sequence',
        store=True
    )
    priority = fields.Integer(
        string='Priority',
        related='deduction_type_id.priority',
        store=True
    )
    
    base_amount = fields.Monetary(
        string='Base Amount',
        currency_field='currency_id',
        help='Amount used as calculation base'
    )
    rate = fields.Float(string='Rate (%)')
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='payslip_id.currency_id'
    )
    
    execution_doc_id = fields.Many2one(
        'hr.execution.document',
        string='Execution Document'
    )
    
    notes = fields.Char(string='Notes')

    is_auto_generated = fields.Boolean(
        string='Auto-generated',
        default=False,
        help='Indicates if this deduction was automatically generated during payslip computation. '
             'Auto-generated deductions are recreated on recomputation, manual ones are preserved.'
    )
