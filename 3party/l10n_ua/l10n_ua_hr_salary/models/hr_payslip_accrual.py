from odoo import models, fields, api


class HrPayslipAccrual(models.Model):
    _name = 'hr.payslip.accrual'
    _description = 'Payslip Accrual'
    _order = 'sequence, id'

    payslip_id = fields.Many2one(
        'hr.payslip',
        string='Payslip',
        required=True,
        ondelete='cascade'
    )
    accrual_type_id = fields.Many2one(
        'hr.accrual.type',
        string='Accrual Type',
        required=True
    )
    sequence = fields.Integer(
        string='Sequence',
        related='accrual_type_id.sequence',
        store=True
    )
    
    quantity = fields.Float(
        string='Quantity',
        default=1.0,
        help='Days, hours, or units'
    )
    rate = fields.Float(
        string='Rate',
        help='Rate per unit (hourly/daily rate)'
    )
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='payslip_id.currency_id'
    )
    
    is_taxable_pdfo = fields.Boolean(
        string='Taxable (PDFO)',
        related='accrual_type_id.is_taxable_pdfo'
    )
    is_military_tax = fields.Boolean(
        string='Military Tax',
        related='accrual_type_id.is_military_tax'
    )
    is_esv_base = fields.Boolean(
        string='ESV Base',
        related='accrual_type_id.is_esv_base'
    )
    is_in_kind = fields.Boolean(
        string='In-Kind Income',
        related='accrual_type_id.is_in_kind'
    )

    d4_income_type = fields.Char(
        string='4DF Income Type',
        related='accrual_type_id.d4_income_type'
    )
    
    notes = fields.Char(string='Notes')

    is_auto_generated = fields.Boolean(
        string='Auto-generated',
        default=False,
        help='Indicates if this accrual was automatically generated during payslip computation. '
             'Auto-generated accruals are recreated on recomputation, manual ones are preserved.'
    )
