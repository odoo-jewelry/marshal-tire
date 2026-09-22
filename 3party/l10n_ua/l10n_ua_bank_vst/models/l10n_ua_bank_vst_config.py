import csv
import io
import logging

from odoo import models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Порядок колонок CSV-виписки iBank 2 UA («Виписки по поточним рахункам»),
# windows-1251, роздільник «;». Перший рядок — шапка.
COL_DATE = 4          # Дата операції: ДД.ММ.РРРР ГГ:ХХ:СС
COL_CORR_ACCOUNT = 8  # Рахунок кореспондента
COL_CORR_EDRPOU = 9   # ЄДРПОУ кореспондента
COL_CORR_NAME = 10    # Кореспондент
COL_DOC_NO = 11       # Номер документа
COL_DEBIT = 13        # Дебет (порожній для кредитових)
COL_CREDIT = 14       # Кредит (порожній для дебетових)
COL_PURPOSE = 15      # Призначення платежу
COL_OP_ID = 17        # Ідентифікатор операції (опційно)


class L10nUaBankSyncConfig(models.Model):
    """Провайдер VST Bank (Банк Восток) — імпорт виписок iBank 2 UA (CSV)."""
    _inherit = 'l10n_ua.bank.sync.config'

    provider = fields.Selection(
        selection_add=[('vst', 'VST Bank (iBank 2 UA)')],
        ondelete={'vst': 'set default'},
    )

    def _fetch_from_bank(self, date_from, date_to):
        if self.provider != 'vst':
            return super()._fetch_from_bank(date_from, date_to)
        raise UserError(_(
            'VST Bank (iBank 2 UA) — файловий провайдер. Використайте майстер '
            '«Імпорт виписки iBank 2 UA», щоб завантажити CSV-файл виписки.'))

    def _source_type(self):
        if self.provider == 'vst':
            return 'file'
        return super()._source_type()

    def _file_to_payload(self, content, filename=None):
        if self.provider == 'vst':
            return {'csv': content.decode('cp1251', 'replace')}
        return super()._file_to_payload(content, filename)

    def action_vst_open_import(self):
        """Відкрити узагальнений майстер імпорту виписки для цього конфігу."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Імпорт виписки з файлу'),
            'res_model': 'l10n_ua.bank.statement.import',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_config_id': self.id},
        }

    @staticmethod
    def _vst_amount(text):
        text = (text or '').strip().replace(' ', '').replace(',', '.')
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def _parse_transactions(self, raw_data):
        if self.provider != 'vst':
            return super()._parse_transactions(raw_data)

        content = (raw_data or {}).get('csv', '')
        reader = csv.reader(io.StringIO(content), delimiter=';', quotechar='"')
        transactions = []
        for idx, row in enumerate(reader):
            if not row or len(row) < COL_CREDIT + 1:
                continue
            # Пропустити рядок-шапку.
            if idx == 0 and row[0].strip().upper().startswith('ЄДРПОУ'):
                continue
            debit = self._vst_amount(row[COL_DEBIT])
            credit = self._vst_amount(row[COL_CREDIT])
            # Кт — надходження (+), Дт — списання (−).
            amount = credit - debit
            if amount == 0.0:
                continue
            raw_date = (row[COL_DATE] or '').strip().split(' ')[0]
            date = ''
            if raw_date:
                parts = raw_date.split('.')
                if len(parts) == 3:
                    date = '%s-%s-%s' % (parts[2], parts[1], parts[0])
            op_id = ''
            if len(row) > COL_OP_ID:
                op_id = (row[COL_OP_ID] or '').strip()
            transactions.append({
                'id': op_id or (row[COL_DOC_NO] or '').strip(),
                'date': date,
                'amount': amount,
                'description': (row[COL_PURPOSE] or '').strip(),
                'partner_name': (row[COL_CORR_NAME] or '').strip(),
                'partner_iban': (row[COL_CORR_ACCOUNT] or '').strip(),
                'partner_edrpou': (row[COL_CORR_EDRPOU] or '').strip(),
            })
        return transactions
