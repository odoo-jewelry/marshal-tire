from odoo import models, fields, _

# Роздільники (у вже декодованому тексті). «ibis» — символ байта 250 (0xFA),
# що в cp1125/cp866 декодується як U+2219 (∙) — класичний роздільник ІБІС/BUH-1.
DELIMITERS = {
    'semicolon': ';',
    'comma': ',',
    'tab': '\t',
    'pipe': '|',
    'ibis': '∙',
}


class L10nUaBankSyncConfig(models.Model):
    """Узагальнений текстовий провайдер виписки (BUH-1 / ІБІС / CSV) — #82.

    Формат банку описується мапінгом колонок у конфізі (роздільник, кодування,
    номери колонок), тож будь-який delimited-текстовий експорт імпортується без
    окремого парсера на кожен банк. Розбір — рідним файловим каркасом
    (_file_to_payload → _parse_transactions → native-виписка).
    """
    _inherit = 'l10n_ua.bank.sync.config'

    provider = fields.Selection(
        selection_add=[('text', 'Generic Text/CSV (BUH-1, ІБІС…)')],
        ondelete={'text': 'set default'},
    )

    text_delimiter = fields.Selection(
        [('semicolon', '; (крапка з комою)'), ('comma', ', (кома)'),
         ('tab', 'Tab'), ('pipe', '| (вертикальна риска)'),
         ('ibis', '∙ ІБІС (ASCII 250)')],
        string='Delimiter', default='semicolon')
    text_encoding = fields.Selection(
        [('cp1251', 'windows-1251'), ('cp1125', 'cp1125 (укр. DOS)'),
         ('cp866', 'cp866 (DOS)'), ('utf-8', 'UTF-8')],
        string='Encoding', default='cp1251')
    text_skip_rows = fields.Integer(
        string='Skip Header Rows', default=0)
    text_date_format = fields.Char(
        string='Date Format', default='%d.%m.%Y',
        help="Формат дати в файлі (strptime), напр. %d.%m.%Y або %Y-%m-%d.")

    # Номери колонок (0-based). -1 = колонка не використовується.
    text_col_date = fields.Integer(string='Date Column', default=0)
    text_col_debit = fields.Integer(string='Debit Column', default=-1)
    text_col_credit = fields.Integer(string='Credit Column', default=-1)
    text_col_amount = fields.Integer(
        string='Signed Amount Column', default=-1,
        help='Колонка суми зі знаком (якщо Дт/Кт не в окремих колонках).')
    text_col_partner = fields.Integer(string='Counterparty Column', default=-1)
    text_col_account = fields.Integer(string='Counterparty Account Column', default=-1)
    text_col_edrpou = fields.Integer(string='Counterparty EDRPOU Column', default=-1)
    text_col_purpose = fields.Integer(string='Purpose Column', default=-1)
    text_col_docid = fields.Integer(string='Document ID Column', default=-1)

    def _source_type(self):
        if self.provider == 'text':
            return 'file'
        return super()._source_type()

    def _file_to_payload(self, content, filename=None):
        if self.provider == 'text':
            enc = self.text_encoding or 'cp1251'
            return {'text': content.decode(enc, 'replace')}
        return super()._file_to_payload(content, filename)

    @staticmethod
    def _text_num(value):
        value = (value or '').strip().replace(' ', '').replace(',', '.')
        if not value:
            return 0.0
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _text_cell(self, cols, index):
        if index is None or index < 0 or index >= len(cols):
            return ''
        return (cols[index] or '').strip().strip('"')

    def _parse_transactions(self, raw_data):
        if self.provider != 'text':
            return super()._parse_transactions(raw_data)

        from datetime import datetime
        text = (raw_data or {}).get('text', '')
        delim = DELIMITERS.get(self.text_delimiter, ';')
        lines = text.splitlines()[self.text_skip_rows or 0:]
        transactions = []
        for line in lines:
            if not line.strip():
                continue
            cols = line.split(delim)
            if self.text_col_amount >= 0:
                amount = self._text_num(self._text_cell(cols, self.text_col_amount))
            else:
                debit = self._text_num(self._text_cell(cols, self.text_col_debit))
                credit = self._text_num(self._text_cell(cols, self.text_col_credit))
                amount = credit - debit
            if amount == 0.0:
                continue
            raw_date = self._text_cell(cols, self.text_col_date)
            date = ''
            if raw_date:
                try:
                    date = datetime.strptime(
                        raw_date, self.text_date_format or '%d.%m.%Y'
                    ).strftime('%Y-%m-%d')
                except ValueError:
                    date = ''
            transactions.append({
                'id': self._text_cell(cols, self.text_col_docid),
                'date': date,
                'amount': amount,
                'description': self._text_cell(cols, self.text_col_purpose),
                'partner_name': self._text_cell(cols, self.text_col_partner),
                'partner_iban': self._text_cell(cols, self.text_col_account),
                'partner_edrpou': self._text_cell(cols, self.text_col_edrpou),
            })
        return transactions
