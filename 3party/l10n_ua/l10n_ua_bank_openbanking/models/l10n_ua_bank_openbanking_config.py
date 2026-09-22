import logging

import requests

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class L10nUaBankSyncConfig(models.Model):
    """Провайдер Open Banking (PSD2 / Berlin Group NextGenPSD2) — #198.

    Стандартизований AISP-доступ (рахунки/баланси/виписки) до багатьох банків
    через один інтерфейс, керування згодами (consents) та ініціювання платежів
    (PISP). Конкретний банк/агрегатор задається `ob_base_url` + OAuth2-креденшли;
    відповіді мапляться зі стандартних Berlin Group-структур.
    """
    _inherit = 'l10n_ua.bank.sync.config'

    provider = fields.Selection(
        selection_add=[('openbanking', 'Open Banking (PSD2)')],
        ondelete={'openbanking': 'set default'},
    )

    ob_base_url = fields.Char(
        string='Open Banking Base URL',
        help='Базовий URL API банку/агрегатора (Berlin Group NextGenPSD2).')
    ob_token_url = fields.Char(
        string='OAuth2 Token URL',
        help='Ендпоінт видачі токена (client_credentials).')
    ob_client_id = fields.Char(string='Client ID')
    ob_client_secret = fields.Char(string='Client Secret')
    ob_account_resource_id = fields.Char(
        string='Account Resource ID',
        help='Ідентифікатор рахунку в API (account-id).')
    ob_consent_id = fields.Char(string='Consent ID')
    ob_consent_valid_until = fields.Date(string='Consent Valid Until')

    # ------------------------------------------------------------------
    # OAuth2 + згоди
    # ------------------------------------------------------------------
    def _ob_get_token(self):
        """Отримати access-токен (client_credentials)."""
        self.ensure_one()
        if not (self.ob_token_url and self.ob_client_id):
            raise UserError(_('Заповніть OAuth2 Token URL та Client ID.'))
        resp = requests.post(self.ob_token_url, data={
            'grant_type': 'client_credentials',
            'client_id': self.ob_client_id,
            'client_secret': self.ob_client_secret or '',
        }, timeout=30)
        resp.raise_for_status()
        token = resp.json().get('access_token')
        if not token:
            raise UserError(_('API не повернув access_token.'))
        return token

    def _ob_headers(self, token):
        headers = {'Authorization': 'Bearer %s' % token, 'Accept': 'application/json'}
        if self.ob_consent_id:
            headers['Consent-ID'] = self.ob_consent_id
        return headers

    def action_check_consent(self):
        """Перевірити чинність згоди за строком дії."""
        self.ensure_one()
        if not self.ob_consent_id:
            raise UserError(_('Немає Consent ID — спершу отримайте згоду.'))
        today = fields.Date.context_today(self)
        if self.ob_consent_valid_until and self.ob_consent_valid_until < today:
            raise UserError(_(
                'Згода недійсна (дійсна до %s). Поновіть згоду.'
            ) % self.ob_consent_valid_until)
        return True

    # ------------------------------------------------------------------
    # AISP: отримання виписки
    # ------------------------------------------------------------------
    def _fetch_from_bank(self, date_from, date_to):
        if self.provider != 'openbanking':
            return super()._fetch_from_bank(date_from, date_to)
        if not (self.ob_base_url and self.ob_account_resource_id):
            raise UserError(_(
                'Заповніть Base URL та Account Resource ID для Open Banking.'))
        self.action_check_consent()
        token = self._ob_get_token()
        url = '%s/v1/accounts/%s/transactions' % (
            self.ob_base_url.rstrip('/'), self.ob_account_resource_id)
        params = {'bookingStatus': 'booked'}
        if date_from:
            params['dateFrom'] = str(date_from)
        if date_to:
            params['dateTo'] = str(date_to)
        resp = requests.get(url, headers=self._ob_headers(token),
                            params=params, timeout=60)
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def _ob_amount(txn):
        raw = (txn.get('transactionAmount') or {}).get('amount', '0')
        try:
            return float(str(raw).replace(' ', ''))
        except (TypeError, ValueError):
            return 0.0

    def _parse_transactions(self, raw_data):
        if self.provider != 'openbanking':
            return super()._parse_transactions(raw_data)

        booked = (((raw_data or {}).get('transactions') or {}).get('booked')
                  or [])
        transactions = []
        for txn in booked:
            amount = self._ob_amount(txn)
            if amount == 0.0:
                continue
            # Списання (−) → контрагент-кредитор; надходження (+) → дебітор.
            if amount < 0:
                name = txn.get('creditorName') or txn.get('debtorName') or ''
                acc = (txn.get('creditorAccount')
                       or txn.get('debtorAccount') or {})
            else:
                name = txn.get('debtorName') or txn.get('creditorName') or ''
                acc = (txn.get('debtorAccount')
                       or txn.get('creditorAccount') or {})
            transactions.append({
                'id': txn.get('transactionId') or txn.get('endToEndId') or '',
                'date': txn.get('bookingDate') or txn.get('valueDate') or '',
                'amount': amount,
                'description': txn.get('remittanceInformationUnstructured')
                or txn.get('remittanceInformationStructured') or '',
                'partner_name': name,
                'partner_iban': acc.get('iban') or acc.get('bban') or '',
                'partner_edrpou': '',
            })
        return transactions

    # ------------------------------------------------------------------
    # PISP: ініціювання платежу (Berlin Group PIS)
    # ------------------------------------------------------------------
    def _ob_payment_payload(self, payer_iban, creditor_name, creditor_iban,
                            amount, currency='UAH', purpose=''):
        """Стандартний payload SEPA/SCT для ініціювання платежу."""
        return {
            'debtorAccount': {'iban': payer_iban},
            'creditorName': creditor_name,
            'creditorAccount': {'iban': creditor_iban},
            'instructedAmount': {'currency': currency, 'amount': '%.2f' % amount},
            'remittanceInformationUnstructured': purpose or '',
        }

    def initiate_payment(self, payer_iban, creditor_name, creditor_iban,
                         amount, currency='UAH', purpose=''):
        """Ініціювати платіж (PISP). Потребує чинної згоди та підпису SCA."""
        self.ensure_one()
        if self.provider != 'openbanking':
            raise UserError(_('Конфігурація не є Open Banking.'))
        if not self.ob_base_url:
            raise UserError(_('Заповніть Base URL для Open Banking.'))
        token = self._ob_get_token()
        url = '%s/v1/payments/sepa-credit-transfers' % self.ob_base_url.rstrip('/')
        payload = self._ob_payment_payload(
            payer_iban, creditor_name, creditor_iban, amount, currency, purpose)
        resp = requests.post(url, headers=self._ob_headers(token),
                             json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()
