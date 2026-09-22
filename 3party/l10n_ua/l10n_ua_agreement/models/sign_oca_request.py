from odoo import fields, models


class SignOcaRequest(models.Model):
    _inherit = 'sign.oca.request'

    def _check_signed(self):
        """Після повного підписання переводимо пов'язаний договір у стан
        «Підписаний» та зберігаємо підписаний PDF."""
        res = super()._check_signed()
        record = self.record_ref
        if self.state == '2_signed' and record and record._name == 'agreement':
            record.sudo().write({
                'state': 'signed',
                'signature_date': fields.Date.context_today(self),
                'signed_document': self.data,
                'signed_filename': self.filename,
            })
        return res
