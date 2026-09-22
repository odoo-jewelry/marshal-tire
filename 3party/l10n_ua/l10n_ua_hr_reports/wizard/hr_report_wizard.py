from odoo import models, fields, api


class HrReportWizard(models.TransientModel):
    _name = 'hr.report.wizard'
    _description = 'HR Report Wizard'

    report_type = fields.Selection([
        ('1df', '1DF (Quarterly Tax Report)'),
        ('d5', 'D5 (ESV Monthly Report)'),
        ('headcount', 'Average Headcount'),
        ('wage_fund', 'Wage Fund Report'),
    ], string='Report Type', required=True, default='1df')
    
    year = fields.Integer(
        string='Year',
        required=True,
        default=lambda self: fields.Date.today().year
    )
    quarter = fields.Selection([
        ('1', 'Q1'),
        ('2', 'Q2'),
        ('3', 'Q3'),
        ('4', 'Q4'),
    ], string='Quarter')
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'),
        ('4', 'April'), ('5', 'May'), ('6', 'June'),
        ('7', 'July'), ('8', 'August'), ('9', 'September'),
        ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month')
    
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )

    def action_generate_report(self):
        self.ensure_one()
        
        if self.report_type == '1df':
            return self._generate_1df()
        elif self.report_type == 'd5':
            return self._generate_d5()
        elif self.report_type == 'headcount':
            return self._generate_headcount()
        elif self.report_type == 'wage_fund':
            return self._generate_wage_fund()

    def _generate_1df(self):
        if not self.quarter:
            return {'type': 'ir.actions.act_window_close'}
        
        existing = self.env['hr.report.1df'].search([
            ('year', '=', self.year),
            ('quarter', '=', self.quarter),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        
        if existing:
            report = existing
        else:
            report = self.env['hr.report.1df'].create({
                'year': self.year,
                'quarter': self.quarter,
                'company_id': self.company_id.id,
            })
        
        report.action_generate()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.report.1df',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _generate_d5(self):
        if not self.month:
            return {'type': 'ir.actions.act_window_close'}
        
        existing = self.env['hr.report.d5'].search([
            ('year', '=', self.year),
            ('month', '=', self.month),
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        
        if existing:
            report = existing
        else:
            report = self.env['hr.report.d5'].create({
                'year': self.year,
                'month': self.month,
                'company_id': self.company_id.id,
            })
        
        report.action_generate()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.report.d5',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _generate_headcount(self):
        if not self.month:
            return {'type': 'ir.actions.act_window_close'}

        existing = self.env['hr.report.headcount'].search([
            ('year', '=', self.year),
            ('month', '=', self.month),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        if existing:
            report = existing
        else:
            report = self.env['hr.report.headcount'].create({
                'year': self.year,
                'month': self.month,
                'company_id': self.company_id.id,
            })

        report.action_generate()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.report.headcount',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _generate_wage_fund(self):
        if not self.month:
            return {'type': 'ir.actions.act_window_close'}

        existing = self.env['hr.report.wage_fund'].search([
            ('year', '=', self.year),
            ('month', '=', self.month),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        if existing:
            report = existing
        else:
            report = self.env['hr.report.wage_fund'].create({
                'year': self.year,
                'month': self.month,
                'company_id': self.company_id.id,
            })

        report.action_generate()

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.report.wage_fund',
            'res_id': report.id,
            'view_mode': 'form',
            'target': 'current',
        }
