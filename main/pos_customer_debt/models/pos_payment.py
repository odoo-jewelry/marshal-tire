from odoo import fields, models


class PosPayment(models.Model):
    _inherit = "pos.payment"

    debt_move_line_ids = fields.One2many(
        "account.move.line",
        "pos_debt_payment_id",
        string="Debt Journal Items",
        readonly=True,
    )


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    pos_debt_payment_id = fields.Many2one(
        "pos.payment",
        string="POS Debt Payment",
        copy=False,
        index=True,
        check_company=True,
        ondelete="set null",
    )
