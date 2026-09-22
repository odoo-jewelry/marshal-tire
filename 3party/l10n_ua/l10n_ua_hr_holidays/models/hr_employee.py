from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    vacation_anchor_date = fields.Date(
        string='Vacation Work-Year Anchor',
        tracking=True,
        help='Date the annual (work-year) vacation seniority is counted from, '
             'when it differs from the hire date. Set by the inter-company '
             'transfer wizard in "Keep Work Year" mode: art. 9 §3 of the '
             'Vacation Law lets the previous employer\'s seniority continue '
             'when the compensation for unused days is transferred along with '
             'the employee. Empty — the work year runs from the hire date.')

    def _get_vacation_anchor_date(self):
        """Carried-over anchor wins over the hire date of the new contract."""
        self.ensure_one()
        return self.vacation_anchor_date or super()._get_vacation_anchor_date()
