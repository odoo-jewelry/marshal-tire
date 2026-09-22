"""Hook into declaration activation — auto-register in eHealth."""
from odoo import models


class L10nUaMedecinDeclaration(models.Model):
    _inherit = 'l10n_ua.medecin.declaration'

    def action_activate(self):
        result = super().action_activate()
        # After activation — try registering in eHealth (in dry-run by default)
        client = self.env['l10n_ua.ehealth.client']
        for rec in self:
            if rec.ehealth_uuid:
                continue
            try:
                uuid = client.post_declaration(rec)
                if uuid:
                    rec.ehealth_uuid = uuid
            except Exception as e:
                # Don't block activation if eHealth is misconfigured;
                # log and let the user re-submit manually.
                rec.message_post(body=f'eHealth: помилка реєстрації — {e}')
        return result
