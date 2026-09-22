from odoo import fields, models


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    agreement_id = fields.Many2one(
        'agreement',
        string='Договір',
        ondelete='restrict',
        index=True,
        copy=False,
        help='Договір, за яким проведено платіж — для взаєморозрахунків '
             'у розрізі договорів.',
    )


class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    def _create_payments(self):
        """Проставити договір на платежі, якщо всі оплачувані рахунки — за одним."""
        payments = super()._create_payments()
        agreements = self.line_ids.mapped('move_id.agreement_id')
        if len(agreements) == 1:
            payments.agreement_id = agreements.id
        return payments
