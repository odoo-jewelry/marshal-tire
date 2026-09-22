from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ua_medecin_ehealth_base_url = fields.Char(
        string='eHealth API URL',
        config_parameter='l10n_ua_medecin_ehealth.base_url',
        help='https://api.ehealth.gov.ua (production) або staging-URL')
    l10n_ua_medecin_ehealth_client_id = fields.Char(
        string='Client ID',
        config_parameter='l10n_ua_medecin_ehealth.client_id')
    l10n_ua_medecin_ehealth_client_secret = fields.Char(
        string='Client Secret',
        config_parameter='l10n_ua_medecin_ehealth.client_secret')
    l10n_ua_medecin_ehealth_dry_run = fields.Boolean(
        string='Тестовий режим (без реальних запитів)',
        config_parameter='l10n_ua_medecin_ehealth.dry_run',
        default=True,
        help='Якщо увімкнено — запити пишуться в лог, але не йдуть в API.')
