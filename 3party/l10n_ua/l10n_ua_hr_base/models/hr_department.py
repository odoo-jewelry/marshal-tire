from odoo import models, fields


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    koatuu_code = fields.Char(
        string='KOATUU Code', size=10,
        help='Code of the Classification of Administrative-Territorial Units of Ukraine')
    department_type = fields.Selection([
        ('head', 'Head Office'),
        ('branch', 'Branch'),
        ('representative', 'Representative Office'),
    ], string='Department Type', default='head')
    is_separate_unit = fields.Boolean(
        string='Separate Unit',
        help='Is a separate structural unit (for PFU reporting)')
    edrpou = fields.Char(
        string='EDRPOU', size=8,
        help='EDRPOU code if the branch is a separate legal entity')
    head_employee_id = fields.Many2one(
        'hr.employee', string='Department Head',
        help='Head of the department')
