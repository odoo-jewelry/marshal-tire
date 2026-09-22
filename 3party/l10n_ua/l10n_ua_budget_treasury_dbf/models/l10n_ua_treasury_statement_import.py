"""Override _parse_custom() для DBF-формату ДКСУ.

Очікувані поля (можна перевизначити через `_dbf_field_map()`):
* `DOC_NUM` / `NUM_DOC` / `N_DOC`  — номер документа
* `DOC_DATE` / `DATA_DOC` / `DATEV` — дата операції
* `SUM` / `SUMA` / `SUM_`           — сума (UAH)
* `NAZ_PRIZ` / `PRIZN` / `PURPOSE`   — призначення платежу
* `KOD_KOR` / `EDRPOU` / `KOD_OS`    — ЄДРПОУ контрагента
* `NAZ_KOR` / `NAZ_OS` / `PARTN`     — назва контрагента
* `DT_KT` / `KOD_OPER`               — D/K (дебет/кредит) — для визначення знаку

Файл звичайно у кодуванні CP866.
"""
from odoo import models, _
from odoo.exceptions import UserError

from .dbf_reader import read_dbf_records, DbfReadError


class L10nUaTreasuryStatementImport(models.TransientModel):
    _inherit = 'l10n_ua.treasury.statement.import'

    def _dbf_field_map(self):
        """Synonyms for known fields. Перевизначити у клієнтському модулі.

        Повертає mapping `canonical_name -> [list_of_possible_dbf_field_names]`.
        Перше знайдене ім'я перемагає.
        """
        return {
            'doc_num':    ['DOC_NUM', 'NUM_DOC', 'N_DOC', 'DOCNO', 'NUMDOC'],
            'doc_date':   ['DOC_DATE', 'DATA_DOC', 'DATEV', 'DATE_DOC', 'DAT', 'DATA'],
            'amount':     ['SUM_', 'SUMA', 'SUM', 'AMOUNT', 'SUM_DOC'],
            'purpose':    ['NAZ_PRIZ', 'PRIZN', 'PRIZNACH', 'PURPOSE', 'PRYZNACH', 'NAZN'],
            'partner_edrpou': ['KOD_KOR', 'EDRPOU', 'KOD_OS', 'KOD_PART', 'OKPO_KOR'],
            'partner_name':   ['NAZ_KOR', 'NAZ_OS', 'PARTN', 'NAZW_KOR', 'KOR_NAME'],
            'direction':  ['DT_KT', 'KOD_OPER', 'DBKR', 'TYPE_OP'],
        }

    def _dbf_extract_row(self, row, mapping):
        """Pull canonical fields from a DBF row dict using the synonym map."""
        out = {}
        for canonical, synonyms in mapping.items():
            for syn in synonyms:
                if syn in row and row[syn] is not None:
                    out[canonical] = row[syn]
                    break
        return out

    def _parse_custom(self, content):
        """Hook called when file_format == 'custom'. Treats `content` as DBF text.

        `content` is already the decoded string; for binary DBF we need raw bytes.
        The framework decodes upstream — so for DBF we re-encode back using
        the encoding the user selected (or fallback latin-1 to preserve bytes).
        """
        encoding = self.encoding or 'cp866'
        try:
            raw = content.encode(encoding, errors='replace')
        except LookupError:
            raise UserError(_('Невідоме кодування %s. Очікується cp866/utf-8.', encoding))

        try:
            records = list(read_dbf_records(raw, encoding=encoding))
        except DbfReadError as e:
            raise UserError(_('Не вдалося прочитати DBF: %s', str(e)))

        if not records:
            raise UserError(_('У DBF не знайдено активних записів.'))

        mapping = self._dbf_field_map()
        out = []
        for row in records:
            r = self._dbf_extract_row(row, mapping)
            if not r.get('doc_date') or r.get('amount') is None:
                continue  # skip malformed
            amount = float(r['amount'])
            # If direction marker is present, use it to set sign convention
            direction = (r.get('direction') or '').strip().upper() if r.get('direction') else None
            if direction in ('D', 'DEBIT', 'ДТ', 'СПИСАН'):
                amount = -abs(amount)
            elif direction in ('K', 'CREDIT', 'КТ', 'НАДХОДЖ'):
                amount = abs(amount)
            out.append({
                'date': r['doc_date'],
                'payment_ref': (r.get('purpose') or '').strip() or _('Виписка ДКСУ'),
                'amount': amount,
                'partner_name': (r.get('partner_name') or '').strip(),
                'ref': str(r.get('doc_num') or '').strip(),
            })
        if not out:
            raise UserError(_(
                'Не вдалося розпізнати жодного рядка. Перевірте маппінг полів '
                'у _dbf_field_map() або сам формат файлу.'))
        return out
