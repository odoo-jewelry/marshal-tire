from odoo import fields, models


class ContractContract(models.Model):
    _inherit = 'contract.contract'

    agreement_id = fields.Many2one(
        'agreement',
        string='Договір',
        ondelete='set null',
        copy=False,
        help='Договір, на підставі якого виставляються періодичні рахунки.',
    )
