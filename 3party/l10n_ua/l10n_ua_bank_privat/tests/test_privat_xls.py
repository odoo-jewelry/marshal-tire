"""Імпорт виписки ПриватБанку з файлу (XLS / XLSX / CSV / MultiCash)."""

import base64
import io
import zipfile
from datetime import date

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError

try:
    import xlwt
except ImportError:  # pragma: no cover
    xlwt = None
try:
    import openpyxl
except ImportError:  # pragma: no cover
    openpyxl = None

HEADERS = ['№ документа', 'Дата операції', 'Час операції', 'Сума', 'Валюта',
           'Призначення платежу', 'ЄДРПОУ/РНОКПП', 'Назва контрагента',
           'Рахунок контрагента', 'МФО контрагента', 'Референс']
# doc, date, time, amount, cur, purpose, edrpou, name, acc, mfo, ref
ROWS = [
    ['Q1', '22.07.2026', '11:33:00', -100000.0, 'UAH', 'Видача готівки',
     14360570, 'Каса', 'UA5030529900000100250207', 305299, 'REF1'],
    ['Q2', '21.07.2026', '09:00:00', 750.0, 'UAH', 'Оплата послуг',
     12345678, 'ТОВ Контрагент', 'UA1112223334445556667', 305299, 'REF2'],
    ['Q3', '20.11.2021', '16:57:00', 500.0, 'UAH', '#ПЕРЕНЕСЕННЯ ЗАЛИШКУ',
     2940910418, 'ФОП', 'UA263333910000026007', 333391, 'REFB'],
]


@tagged('post_install', '-at_install')
class TestPrivatFileImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env['account.journal'].create({
            'name': 'Privat File', 'type': 'bank', 'code': 'PFIL',
            'company_id': cls.env.company.id})
        cls.cfg = cls.env['l10n_ua.bank.sync.config'].create({
            'name': 'Privat File', 'provider': 'privat_xls',
            'journal_id': cls.journal.id})

    def _parse(self, content):
        payload = self.cfg._file_to_payload(content, 'stmt')
        self.assertIn('privat_xls_b64', payload)
        return self.cfg._parse_transactions(payload)

    def _assert_two_real(self, txs):
        # 2 реальні операції; рядок #ПЕРЕНЕСЕННЯ ЗАЛИШКУ пропущено
        self.assertEqual(len(txs), 2)
        self.assertFalse(any('ПЕРЕНЕСЕННЯ' in t['description'] for t in txs))
        by_id = {t['id']: t for t in txs}
        # знаки збережено
        self.assertTrue(any(t['amount'] < 0 for t in txs))
        self.assertTrue(any(t['amount'] > 0 for t in txs))
        return by_id

    # ---- builders ----

    def _xls_bytes(self):
        wb = xlwt.Workbook()
        sh = wb.add_sheet('Лист1')
        sh.write(0, 0, 'АТ КБ "ПРИВАТБАНК"')
        for c, h in enumerate(HEADERS):
            sh.write(2, c, h)
        for i, row in enumerate(ROWS):
            for c, v in enumerate(row):
                sh.write(3 + i, c, v)
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue()

    def _xlsx_bytes(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['АТ КБ "ПРИВАТБАНК"'])
        ws.append([])
        ws.append(HEADERS)
        for row in ROWS:
            ws.append(row)
        bio = io.BytesIO()
        wb.save(bio)
        return bio.getvalue()

    def _csv_bytes(self):
        # ЄДРПОУ;МФО;Рахунок;Валюта;№док;Дата;МФО банку;Назва банку;
        # Рахунок кор.;ЄДРПОУ кор.;Кореспондент;Сума;Призначення;
        head = ('ЄДРПОУ;МФО;Рахунок;Валюта;Номер документу;Дата операції;'
                'МФО банку;Назва банку;Рахунок кореспондента;'
                'ЄДРПОУ кореспондента;Кореспондент;Сума;Призначення платежу;')
        lines = [head,
                 '2940910418;305299;UA123;UAH;Q1;22.07.2026;305299;АТ КБ;'
                 'UA5030529900000100250207;14360570;Каса;-100 000.00;Видача готівки;',
                 '2940910418;305299;UA123;UAH;Q2;21.07.2026;305299;АТ КБ;'
                 'UA1112223334445556667;12345678;ТОВ Контрагент;750,00;Оплата послуг;',
                 '2940910418;305299;UA123;UAH;Q3;20.11.2021;333391;АТ КБ;'
                 'UA263333910000026007;2940910418;ФОП;500.00;#ПЕРЕНЕСЕННЯ ЗАЛИШКУ;']
        return '\r\n'.join(lines).encode('cp1251')

    def _multicash_zip_bytes(self):
        # umsatz: acc[1], date[3], purpose[5], flag[8], doc[9], amount[10], …name
        umsatz = '\r\n'.join([
            '305299;UA123;203;22.07.2026; ;Видача готівки; ; ;D;Q1;-100000.00; ; ;'
            '22.07.2026; ; ;{{DABR=RVHI}}; ; ;Каса',
            '305299;UA123;203;21.07.2026; ;Оплата послуг; ; ;C;Q2;750.00; ; ;'
            '21.07.2026; ; ; ; ; ;ТОВ Контрагент',
            '305299;UA123;1;20.11.2021; ;#ПЕРЕНЕСЕННЯ ЗАЛИШКУ; ; ;C;Q3;500.00; ; ;'
            '20.11.2021; ; ; ; ; ;ФОП',
        ]).encode('cp1251')
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, 'w') as zf:
            zf.writestr('umsatz.txt', umsatz)
            zf.writestr('auszug.txt',
                        '305299;UA123;1;01.01.2021;UAH;0;0;0;0;ФОП;'.encode('cp1251'))
        return bio.getvalue()

    # ---- tests ----

    def test_source_type_is_file(self):
        self.assertEqual(self.cfg._source_type(), 'file')
        self.assertEqual(self.cfg.exchange_type, 'file')

    def test_fetch_from_bank_blocked(self):
        with self.assertRaises(UserError):
            self.cfg._fetch_from_bank(date(2026, 7, 1), date(2026, 7, 31))

    def test_xls(self):
        if xlwt is None:
            self.skipTest('xlwt not installed')
        by_id = self._assert_two_real(self._parse(self._xls_bytes()))
        self.assertAlmostEqual(by_id['REF1']['amount'], -100000.0, places=2)
        self.assertEqual(by_id['REF1']['date'], '2026-07-22')
        self.assertEqual(by_id['REF1']['partner_edrpou'], '14360570')
        self.assertEqual(by_id['REF1']['partner_iban'], 'UA5030529900000100250207')

    def test_xlsx(self):
        if openpyxl is None:
            self.skipTest('openpyxl not installed')
        by_id = self._assert_two_real(self._parse(self._xlsx_bytes()))
        self.assertAlmostEqual(by_id['REF1']['amount'], -100000.0, places=2)
        self.assertEqual(by_id['REF2']['date'], '2026-07-21')

    def test_csv(self):
        by_id = self._assert_two_real(self._parse(self._csv_bytes()))
        # № документа у CSV → id
        self.assertAlmostEqual(by_id['Q1']['amount'], -100000.0, places=2)
        # сума з пробілами-роздільниками та з комою
        self.assertAlmostEqual(by_id['Q2']['amount'], 750.0, places=2)
        self.assertEqual(by_id['Q1']['partner_name'], 'Каса')
        self.assertEqual(by_id['Q1']['partner_edrpou'], '14360570')

    def test_multicash_zip(self):
        txs = self._parse(self._multicash_zip_bytes())
        by_id = self._assert_two_real(txs)
        self.assertAlmostEqual(by_id['Q1']['amount'], -100000.0, places=2)
        self.assertAlmostEqual(by_id['Q2']['amount'], 750.0, places=2)
        self.assertEqual(by_id['Q1']['date'], '2026-07-22')
        self.assertEqual(by_id['Q1']['partner_name'], 'Каса')

    def test_dbf_unsupported(self):
        # dBase III/FoxBase magic → дружня помилка, не виняток парсера
        with self.assertRaises(UserError):
            self._parse(b'\x30' + b'\x00' * 40)

    def test_opening_balance_extracted(self):
        # Рядок #ПЕРЕНЕСЕННЯ ЗАЛИШКУ (500) стає вхідним залишком, а не рухом;
        # вихідний = вхідний + Σ рухів (-100000 + 750).
        cases = [('xls', self._xls_bytes, xlwt),
                 ('xlsx', self._xlsx_bytes, openpyxl),
                 ('csv', self._csv_bytes, True),
                 ('multicash', self._multicash_zip_bytes, True)]
        expected_closing = 500.0 + (-100000.0 + 750.0)
        for name, builder, need in cases:
            if need is None:
                continue
            payload = self.cfg._file_to_payload(builder(), 'stmt')
            opening, closing = self.cfg._extract_balances(payload)
            self.assertAlmostEqual(opening, 500.0, places=2, msg=name)
            self.assertAlmostEqual(closing, expected_closing, places=2, msg=name)
