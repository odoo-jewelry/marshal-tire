from odoo import api, fields, models


class L10nUaTaxPeriod(models.Model):
    _name = 'l10n_ua.tax.period'
    _description = 'Tax Period'
    _order = 'date_start desc'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
    )
    period_type = fields.Selection(
        selection=[
            ('month', 'Month'),
            ('quarter', 'Quarter'),
            ('year', 'Year'),
        ],
        string='Period Type',
        required=True,
    )
    date_start = fields.Date(
        string='Start Date',
        required=True,
    )
    date_end = fields.Date(
        string='End Date',
        required=True,
    )
    year = fields.Integer(
        string='Year',
        compute='_compute_year',
        store=True,
    )
    quarter = fields.Integer(
        string='Quarter',
        compute='_compute_quarter',
        store=True,
    )
    month = fields.Integer(
        string='Month',
        compute='_compute_month',
        store=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('closed', 'Closed'),
        ],
        string='State',
        default='open',
    )

    @api.depends('period_type', 'date_start')
    def _compute_name(self):
        for record in self:
            if record.date_start:
                if record.period_type == 'month':
                    record.name = record.date_start.strftime('%m/%Y')
                elif record.period_type == 'quarter':
                    q = (record.date_start.month - 1) // 3 + 1
                    record.name = f'Q{q}/{record.date_start.year}'
                else:
                    record.name = str(record.date_start.year)
            else:
                record.name = 'New'

    @api.depends('date_start')
    def _compute_year(self):
        for record in self:
            record.year = record.date_start.year if record.date_start else 0

    @api.depends('date_start')
    def _compute_quarter(self):
        for record in self:
            if record.date_start:
                record.quarter = (record.date_start.month - 1) // 3 + 1
            else:
                record.quarter = 0

    @api.depends('date_start')
    def _compute_month(self):
        for record in self:
            record.month = record.date_start.month if record.date_start else 0

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'open'})
