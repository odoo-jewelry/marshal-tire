import base64
import logging
import requests
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Розкладка колонок виписки Приват24 Бізнес (експорт XLS, BIFF8).
# Шапка таблиці — рядок з «№ документа» у колонці 0; дані — далі.
PRIVAT_XLS_COL_DOC = 0        # № документа
PRIVAT_XLS_COL_DATE = 1       # Дата операції (ДД.ММ.РРРР)
PRIVAT_XLS_COL_AMOUNT = 3     # Сума (знакова: − списання, + надходження)
PRIVAT_XLS_COL_PURPOSE = 5    # Призначення платежу
PRIVAT_XLS_COL_EDRPOU = 6     # ЄДРПОУ/РНОКПП контрагента
PRIVAT_XLS_COL_CNTR_NAME = 7  # Назва контрагента
PRIVAT_XLS_COL_CNTR_ACC = 8   # Рахунок контрагента
PRIVAT_XLS_COL_REF = 10       # Референс


class L10nUaBankSyncConfig(models.Model):
    """Extend base config with PrivatBank provider (online API + XLS file)."""
    _inherit = 'l10n_ua.bank.sync.config'

    provider = fields.Selection(
        selection_add=[
            ('privat', 'PrivatBank'),
            ('privat_xls', 'PrivatBank (файл виписки)'),
        ],
        ondelete={'privat': 'set default', 'privat_xls': 'set default'},
    )

    # PrivatBank API Credentials
    privat_api_token = fields.Char(
        string='API Token',
        help='Token from Privat24 Business Autoclient',
    )
    privat_account_iban = fields.Char(
        string='Account IBAN',
        help='Account IBAN (UA + 27 digits)',
    )

    # Legacy Merchant API
    privat_merchant_id = fields.Char(
        string='Merchant ID',
        help='Legacy merchant ID (for old API)',
    )
    privat_merchant_password = fields.Char(
        string='Merchant Password',
        help='Legacy merchant password (for old API)',
    )
    privat_card_number = fields.Char(
        string='Card Number',
        help='Card number for statement retrieval (16 digits)',
    )

    def _source_type(self):
        if self.provider == 'privat_xls':
            return 'file'
        return super()._source_type()

    def _fetch_from_bank(self, date_from, date_to):
        """Fetch statements from PrivatBank API."""
        self.ensure_one()

        if self.provider == 'privat_xls':
            raise UserError(_(
                'PrivatBank (файл виписки) — файловий провайдер. Скористайтесь '
                'майстром «Імпорт виписки з файлу», щоб завантажити файл виписки '
                'з Приват24 Бізнес (XLS / XLSX / CSV / MultiCash-ZIP).'))

        if self.provider != 'privat':
            return super()._fetch_from_bank(date_from, date_to)

        if self.privat_api_token:
            return self._privat_fetch_autoclient(date_from, date_to)
        elif self.privat_merchant_id:
            return self._privat_fetch_merchant(date_from, date_to)
        else:
            raise UserError(_("Please configure PrivatBank API Token or Merchant credentials"))

    def _privat_fetch_autoclient(self, date_from, date_to):
        """Fetch via Autoclient API (token-based)."""
        _logger.info("PrivatBank: Using Autoclient API")

        url = "https://acp.privatbank.ua/api/statements/transactions"

        headers = {
            'Content-Type': 'application/json',
            'token': self.privat_api_token,
        }

        params = {
            'startDate': date_from.strftime('%d-%m-%Y'),
            'endDate': date_to.strftime('%d-%m-%Y'),
        }

        if self.privat_account_iban:
            params['acc'] = self.privat_account_iban

        _logger.info("PrivatBank: Fetching %s with params %s", url, params)

        response = requests.get(url, headers=headers, params=params, timeout=60)

        _logger.info("PrivatBank: Response status %s", response.status_code)

        if response.status_code != 200:
            raise UserError(_("PrivatBank API error: %s") % response.text)

        data = response.json()

        # Return full response for storage
        return {
            'api_type': 'autoclient',
            'url': url,
            'params': params,
            'response': data,
        }

    def _privat_fetch_merchant(self, date_from, date_to):
        """Fetch via legacy Merchant API."""
        _logger.info("PrivatBank: Using Merchant API")

        if not self.privat_card_number:
            raise UserError(_("Card number is required for Merchant API"))

        url = "https://api.privatbank.ua/p24api/rest_fiz"

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <request version="1.0">
            <merchant>
                <id>{self.privat_merchant_id}</id>
                <signature></signature>
            </merchant>
            <data>
                <oper>cmt</oper>
                <wait>0</wait>
                <test>0</test>
                <payment id="">
                    <prop name="sd" value="{date_from.strftime('%d.%m.%Y')}"/>
                    <prop name="ed" value="{date_to.strftime('%d.%m.%Y')}"/>
                    <prop name="card" value="{self.privat_card_number}"/>
                </payment>
            </data>
        </request>"""

        response = requests.post(url, data=xml_data, timeout=60)

        if response.status_code != 200:
            raise UserError(_("PrivatBank Merchant API error"))

        return {
            'api_type': 'merchant',
            'url': url,
            'response_text': response.text,
        }

    # ------------------------------------------------------------------
    # PrivatBank XLS file provider (Приват24 Бізнес → експорт XLS)
    # ------------------------------------------------------------------

    def _file_to_payload(self, content, filename=None):
        """Байти файлу виписки → JSON-безпечний payload (base64)."""
        if self.provider == 'privat_xls':
            return {'privat_xls_b64': base64.b64encode(content).decode('ascii')}
        return super()._file_to_payload(content, filename)

    def _extract_balances(self, raw_data):
        """Вхідний/вихідний залишок з файлу виписки ПриватБанку.

        Вхідний залишок = сума рядка «#ПЕРЕНЕСЕННЯ ЗАЛИШКУ»; вихідний =
        вхідний + Σ рухів. Так виписка отримує коректний balance_start, і
        показаний кінцевий баланс збігається з реальним (а не лише Σ рухів).
        """
        if self.provider != 'privat_xls':
            return super()._extract_balances(raw_data)
        transactions, opening = self._privat_file_parse(raw_data)
        if opening is None:
            return (None, None)
        closing = round(opening + sum(t['amount'] for t in transactions), 2)
        return (opening, closing)

    def action_privat_xls_open_import(self):
        """Відкрити майстер імпорту виписки XLS для цього конфігу."""
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
    def _privat_cell(value):
        """Клітинку у рядок: цілі float ('14360570.0') → '14360570'."""
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip()

    @staticmethod
    def _privat_amount(value):
        """Знакова сума: приймає число або текст ('-100 000.00', '750,00')."""
        if isinstance(value, (int, float)):
            return float(value)
        text = (str(value).strip().replace(' ', '').replace('\xa0', '')
                .replace(',', '.'))
        try:
            return float(text)
        except ValueError:
            return 0.0

    @staticmethod
    def _privat_date(raw):
        """'ДД.ММ.РРРР' → 'РРРР-ММ-ДД'; '' якщо не дата."""
        raw = (raw or '').strip()
        if not raw or '.' not in raw:
            return ''
        parts = raw.split('.')
        if len(parts) != 3:
            return ''
        return '%s-%s-%s' % (parts[2], parts[1], parts[0])

    @staticmethod
    def _privat_is_carry(purpose):
        """Технічний рядок перенесення вхідного залишку — не рух коштів."""
        return (purpose or '').strip().startswith('#ПЕРЕНЕСЕННЯ ЗАЛИШКУ')

    def _privat_file_parse(self, raw_data):
        """Автовизначення формату файлу виписки ПриватБанку та розбір.

        Повертає ``(transactions, opening_balance)`` — вхідний залишок беремо з
        рядка «#ПЕРЕНЕСЕННЯ ЗАЛИШКУ» (None, якщо його немає).

        Підтримка: XLS (BIFF8), XLSX, CSV (Приват24, cp1251), MultiCash (ZIP з
        umsatz.txt/auszug.txt). DBF наразі не підтримується.
        """
        b64 = (raw_data or {}).get('privat_xls_b64', '')
        if not b64:
            return ([], None)
        content = base64.b64decode(b64)

        if content[:4] == b'PK\x03\x04':
            # ZIP: MultiCash (umsatz.txt) або XLSX (xl/…).
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                names = zf.namelist()
                umsatz = next((n for n in names
                               if n.lower().endswith('umsatz.txt')), None)
                if umsatz:
                    return self._privat_parse_multicash(
                        zf.read(umsatz).decode('cp1251', 'replace'))
                if any(n.startswith('xl/') for n in names):
                    return self._privat_parse_xlsx(content)
            raise UserError(_(
                'ZIP-файл не схожий ні на MultiCash (umsatz.txt), ні на XLSX.'))
        if content[:4] == b'\xd0\xcf\x11\xe0':
            return self._privat_parse_xls(content)
        if content[:1] in (b'\x03', b'\x30', b'\x83', b'\x8b', b'\xf5', b'\xfb'):
            raise UserError(_(
                'Формат DBF поки не підтримується. Скористайтесь XLS/XLSX/CSV '
                'або MultiCash-випискою з Приват24 Бізнес.'))
        # Інакше — текст (CSV Приват24, cp1251).
        return self._privat_parse_csv(content.decode('cp1251', 'replace'))

    def _privat_parse_xls(self, content):
        """XLS (BIFF8) через xlrd — табличний експорт Приват24 Бізнес."""
        import xlrd
        book = xlrd.open_workbook(file_contents=content)
        sheet = book.sheet_by_index(0)
        rows = [[sheet.cell_value(r, c) for c in range(sheet.ncols)]
                for r in range(sheet.nrows)]
        return self._privat_parse_table_rows(rows)

    def _privat_parse_xlsx(self, content):
        """XLSX через openpyxl — та сама розкладка колонок, що й XLS."""
        import io
        import openpyxl
        wb = openpyxl.load_workbook(
            io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        rows = [[('' if v is None else v) for v in row]
                for row in ws.iter_rows(values_only=True)]
        return self._privat_parse_table_rows(rows)

    def _privat_parse_table_rows(self, rows):
        """Спільний розбір табличного експорту (XLS/XLSX).

        Колонки: №документа, дата, час, знакова сума, валюта, призначення,
        ЄДРПОУ, контрагент, рахунок к/а, МФО, референс.

        Шапки/інфо-блок і підсумки визначаємо не за назвою колонки (XLSX-експорт
        її не має), а за змістом: транзакція — рядок, де колонка дати містить
        коректну дату ДД.ММ.РРРР. Решта (текст «Дата операції», порожні,
        підсумкові рядки) відсіюється автоматично.
        """
        transactions = []
        opening = None
        for row in rows:
            if len(row) <= PRIVAT_XLS_COL_REF:
                continue
            date = self._privat_date(str(row[PRIVAT_XLS_COL_DATE]))
            if not date:
                continue
            purpose = str(row[PRIVAT_XLS_COL_PURPOSE]).strip()
            if self._privat_is_carry(purpose):
                # Вхідний залишок — не рух коштів.
                opening = self._privat_amount(row[PRIVAT_XLS_COL_AMOUNT])
                continue
            doc = self._privat_cell(row[PRIVAT_XLS_COL_DOC])
            ref = self._privat_cell(row[PRIVAT_XLS_COL_REF])
            transactions.append({
                'id': ref or doc,
                'date': date,
                'amount': self._privat_amount(row[PRIVAT_XLS_COL_AMOUNT]),
                'description': purpose,
                'partner_name': self._privat_cell(row[PRIVAT_XLS_COL_CNTR_NAME]),
                'partner_iban': self._privat_cell(row[PRIVAT_XLS_COL_CNTR_ACC]),
                'partner_edrpou': self._privat_cell(row[PRIVAT_XLS_COL_EDRPOU]),
            })
        return transactions, opening

    def _privat_parse_csv(self, text):
        """CSV Приват24 Бізнес (cp1251, роздільник «;»).

        Колонки: ЄДРПОУ; МФО; Рахунок; Валюта; №документу; Дата; МФО банку;
        Назва банку; Рахунок кор.; ЄДРПОУ кор.; Кореспондент; Сума;
        Призначення платежу.
        """
        import csv
        import io
        C_DOC, C_DATE, C_ACC, C_EDRPOU, C_NAME, C_AMOUNT, C_PURPOSE = \
            4, 5, 8, 9, 10, 11, 12
        reader = csv.reader(io.StringIO(text), delimiter=';', quotechar='"')
        transactions = []
        opening = None
        for idx, row in enumerate(reader):
            if len(row) <= C_PURPOSE:
                continue
            if idx == 0 and 'Дата' in row[C_DATE]:
                continue  # шапка
            date = self._privat_date(row[C_DATE])
            if not date:
                continue
            purpose = (row[C_PURPOSE] or '').strip()
            if self._privat_is_carry(purpose):
                opening = self._privat_amount(row[C_AMOUNT])
                continue
            transactions.append({
                'id': (row[C_DOC] or '').strip(),
                'date': date,
                'amount': self._privat_amount(row[C_AMOUNT]),
                'description': purpose,
                'partner_name': (row[C_NAME] or '').strip(),
                'partner_iban': (row[C_ACC] or '').strip(),
                'partner_edrpou': (row[C_EDRPOU] or '').strip(),
            })
        return transactions, opening

    def _privat_parse_multicash(self, text):
        """MultiCash umsatz.txt (cp1251, «;»).

        Значущі поля: [1] рахунок, [3] дата, [5] призначення, [9] №документа,
        [10] знакова сума; назва контрагента — останнє непорожнє поле (не тег
        {{…}}).
        """
        M_ACC, M_DATE, M_PURPOSE, M_DOC, M_AMOUNT = 1, 3, 5, 9, 10
        transactions = []
        opening = None
        for line in text.splitlines():
            if not line.strip():
                continue
            fields = line.split(';')
            if len(fields) <= M_AMOUNT:
                continue
            date = self._privat_date(fields[M_DATE])
            if not date:
                continue
            purpose = (fields[M_PURPOSE] or '').strip()
            if self._privat_is_carry(purpose):
                opening = self._privat_amount(fields[M_AMOUNT])
                continue
            partner_name = next(
                (f.strip() for f in reversed(fields)
                 if f.strip() and not f.strip().startswith('{{')), '')
            transactions.append({
                'id': (fields[M_DOC] or '').strip(),
                'date': date,
                'amount': self._privat_amount(fields[M_AMOUNT]),
                'description': purpose,
                'partner_name': partner_name,
                'partner_iban': '',
                'partner_edrpou': '',
            })
        return transactions, opening

    def _parse_transactions(self, raw_data):
        """Parse PrivatBank API response into transaction list."""
        self.ensure_one()

        if self.provider == 'privat_xls':
            return self._privat_file_parse(raw_data)[0]

        if self.provider != 'privat':
            return super()._parse_transactions(raw_data)

        api_type = raw_data.get('api_type')

        if api_type == 'autoclient':
            return self._privat_parse_autoclient(raw_data.get('response', {}))
        elif api_type == 'merchant':
            return self._privat_parse_merchant(raw_data.get('response_text', ''))
        else:
            return []

    def _privat_parse_autoclient(self, data):
        """Parse Autoclient API response."""
        transactions = []

        # Handle different response formats
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('transactions', []) or data.get('statements', []) or []
        else:
            return []

        for item in items:
            trans = {
                'id': item.get('ID') or item.get('REF') or item.get('id', ''),
                'date': item.get('DATE_TIME_DAT_OD_TIM_P') or item.get('TRANDATE') or item.get('date', ''),
                'amount': self._privat_parse_amount(item),
                'description': item.get('OSND') or item.get('purpose') or item.get('description', ''),
                'partner_name': item.get('CNTR_NAME') or item.get('AUT_CNTR_NAM', ''),
                'partner_iban': item.get('CNTR_ACC') or item.get('AUT_CNTR_ACC', ''),
                'partner_edrpou': item.get('CNTR_CRF') or item.get('AUT_CNTR_CRF', ''),
            }
            transactions.append(trans)

        return transactions

    def _privat_parse_merchant(self, xml_text):
        """Parse Merchant API XML response."""
        import xml.etree.ElementTree as ET

        transactions = []

        try:
            root = ET.fromstring(xml_text)

            for statement in root.findall('.//statement'):
                amount_str = statement.get('cardamount', '0')
                amount = self._privat_clean_amount(amount_str)

                trans = {
                    'id': statement.get('refp', ''),
                    'date': statement.get('trandate', ''),
                    'amount': amount,
                    'description': statement.get('description', ''),
                    'partner_name': '',
                    'partner_iban': '',
                    'partner_edrpou': '',
                }
                transactions.append(trans)

        except ET.ParseError as e:
            _logger.error("PrivatBank: XML parse error: %s", str(e))

        return transactions

    def _privat_parse_amount(self, item):
        """
        Parse amount from API response item.

        Returns signed amount:
        - Positive = incoming (credit to account, Кт)
        - Negative = outgoing (debit from account, Дт)

        PrivatBank Autoclient API uses TRANTYPE field:
        - TRANTYPE: "C" = Credit (incoming)
        - TRANTYPE: "D" = Debit (outgoing)
        """
        # Try different field names for amount
        amount_str = (
            item.get('SUM') or
            item.get('SUMA') or
            item.get('SUM_E') or
            item.get('amount') or
            item.get('cardamount') or
            '0'
        )
        amount = self._privat_clean_amount(amount_str)

        # Determine direction (debit/credit)

        # Method 1: Check TRANTYPE field (PrivatBank Autoclient API)
        # "C" = Credit (incoming), "D" = Debit (outgoing)
        trantype = str(item.get('TRANTYPE', '')).upper()
        if trantype == 'D':
            return -abs(amount)  # Debit = outgoing = negative
        elif trantype == 'C':
            return abs(amount)   # Credit = incoming = positive

        # Method 2: Check DEBIT flag (1 = outgoing/debit, 0 = incoming/credit)
        debit_flag = item.get('DEBIT')
        if debit_flag is not None:
            if str(debit_flag) == '1':
                return -abs(amount)  # Outgoing = negative
            else:
                return abs(amount)   # Incoming = positive

        # Method 3: Check BPL field ("D" = debit, "C" = credit)
        bpl = item.get('BPL', '').upper()
        if bpl == 'D':
            return -abs(amount)  # Debit = outgoing = negative
        elif bpl == 'C':
            return abs(amount)   # Credit = incoming = positive

        # Method 4: Check if amount string already has sign
        # (some API responses include "-" for outgoing)
        if isinstance(amount_str, str) and amount_str.strip().startswith('-'):
            return -abs(amount)

        # Method 5: Compare accounts - if MY_ACC is sender, it's outgoing
        my_acc = item.get('AUT_MY_ACC', '')
        # If OSND (description) contains patterns indicating outgoing
        osnd = str(item.get('OSND', '')).lower()
        if any(pattern in osnd for pattern in ['комісія', 'списання', 'оплата', 'переказ']):
            # Check if it's not an incoming transfer
            if 'зарахування' not in osnd and 'надходження' not in osnd:
                return -abs(amount)

        # Default: return positive (assume incoming if unknown)
        return abs(amount)

    def _privat_clean_amount(self, amount_str):
        """Clean and convert amount string to float."""
        if isinstance(amount_str, (int, float)):
            return float(amount_str)

        # Remove spaces, currency suffixes, convert comma to dot
        amount_str = str(amount_str).replace(' ', '').replace(',', '.')
        # Remove non-numeric characters except minus and dot
        cleaned = ''.join(c for c in amount_str if c.isdigit() or c in '.-')

        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    def action_test_connection(self):
        """Test PrivatBank API connection."""
        self.ensure_one()

        if self.provider != 'privat':
            return super().action_test_connection()

        if not self.privat_api_token:
            raise UserError(_("Please configure API Token"))

        try:
            # Use balance endpoint with today's date
            url = "https://acp.privatbank.ua/api/statements/balance"
            headers = {
                'Content-Type': 'application/json',
                'token': self.privat_api_token,
            }
            today = datetime.now().strftime('%d-%m-%Y')
            params = {
                'startDate': today,
                'endDate': today,
            }
            if self.privat_account_iban:
                params['acc'] = self.privat_account_iban

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                # Try to get account info from response
                balances = data.get('balances', [])
                if balances:
                    acc_info = balances[0]
                    message = _('Connected! Account: %s, Balance: %s %s') % (
                        acc_info.get('acc', 'N/A'),
                        acc_info.get('balanceOut', 'N/A'),
                        acc_info.get('currency', 'UAH'),
                    )
                else:
                    message = _('Connection to PrivatBank API successful!')
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': message,
                        'type': 'success',
                    }
                }
            else:
                raise UserError(_("API returned error: %s") % response.text)

        except requests.exceptions.RequestException as e:
            raise UserError(_("Connection failed: %s") % str(e))
