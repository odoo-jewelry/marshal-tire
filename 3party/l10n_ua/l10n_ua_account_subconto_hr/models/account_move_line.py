"""HR department as a subconto dimension on journal items."""

from odoo import models, fields


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    subconto_department_id = fields.Many2one(
        'hr.department',
        string='Department (Subconto)',
        compute='_compute_subconto_quick_fields',
        inverse='_inverse_subconto_department',
        store=True,
    )

    def _subconto_quick_fields_map(self):
        return {
            **super()._subconto_quick_fields_map(),
            'hr.department': 'subconto_department_id',
        }

    def _inverse_subconto_department(self):
        self._set_subconto_value('hr.department', 'subconto_department_id')
