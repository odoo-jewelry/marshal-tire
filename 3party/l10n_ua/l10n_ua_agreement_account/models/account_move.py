from odoo import fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    agreement_id = fields.Many2one(
        'agreement',
        string='Договір',
        ondelete='restrict',
        tracking=True,
        index=True,
        copy=False,
        help='Договір, у розрізі якого ведуться взаєморозрахунки за цим '
             'документом. Успадковується із замовлення на продаж.',
    )


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    agreement_id = fields.Many2one(
        'agreement',
        string='Договір',
        related='move_id.agreement_id',
        store=True,
        index=True,
        help='Договір проводки (з документа) — для ОСВ 361/631 та '
             'взаєморозрахунків у розрізі договорів.',
    )
