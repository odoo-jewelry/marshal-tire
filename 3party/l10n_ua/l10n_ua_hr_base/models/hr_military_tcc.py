from odoo import models, fields


class HrMilitaryTcc(models.Model):
    _name = 'hr.military.tcc'
    _description = 'Territorial Recruitment Center (TCC)'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    region_id = fields.Many2one('res.country.state', string='Region',
                                 domain="[('country_id.code', '=', 'UA')]")
    address = fields.Text(string='Address')
    phone = fields.Char(string='Phone')
    email = fields.Char(string='Email')
    active = fields.Boolean(string='Active', default=True)
