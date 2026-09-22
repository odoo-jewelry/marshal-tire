from odoo import models, fields, api


class HrOrderTemplate(models.Model):
    _name = 'hr.order.template'
    _description = 'HR Order Template'
    _order = 'sequence, name'

    name = fields.Char(string='Template Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    order_type = fields.Selection([
        ('hiring', 'Hiring'),
        ('dismissal', 'Dismissal'),
        ('transfer', 'Transfer'),
        ('vacation', 'Vacation'),
        ('bonus', 'Bonus'),
        ('sick_leave', 'Sick Leave'),
        ('business_trip', 'Business Trip'),
        ('other', 'Other'),
    ], string='Order Type', required=True)

    subject = fields.Char(string='Subject')
    body = fields.Html(string='Body', sanitize=False)
    active = fields.Boolean(string='Active', default=True)

    notes = fields.Text(string='Notes')
