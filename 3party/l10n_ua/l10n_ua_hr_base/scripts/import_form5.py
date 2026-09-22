"""Імпорт заповненого бланка «Списки персонального військового обліку» в Odoo.

Багато закладів ведуть додаток 5 в Excel і переходять на Odoo вже з готовим
файлом. Скрипт читає такий бланк (експортований у CSV) і розкладає його по
військово-облікових полях `hr.employee`.

Запуск:
    soffice --headless --convert-to csv Списки.xls        # якщо файл ще .xls
    sudo -u odoo HOME=/tmp /opt/odoo/venv/bin/odoo shell \\
        -c /opt/odoo/odoo.conf -d <db> --no-http < import_form5.py

Змінні середовища:
    FORM5_CSV    — шлях до CSV (типово /opt/odoo/import_data/form5.csv)
    FORM5_APPLY  — «1», щоб записати зміни; без неї скрипт лише показує звіт
                   (сухий прогін — типова поведінка, бо зіставлення за ПІБ
                   ніколи не буває стовідсотковим)

Колонки очікуються в порядку граф бланка (0-based індекси CSV):
    0 №, 1 категорія, 2 звання, 3 ПІБ, 4 дата народження,
    5 реєстраційний номер запису в ЄДР, 6 РНОКПП, 7 ВОС, 8 реквізити ВОД,
    9 паспорт, 10 адреса, 12 ТЦК, 14 відстрочка, 15 спецоблік,
    16 військова служба, 17 мобілізаційне розпорядження,
    18 посада та наказ, 19 реквізити повідомлення
"""

import csv
import difflib
import os
import re
from datetime import datetime

CSV_PATH = os.environ.get('FORM5_CSV', '/opt/odoo/import_data/form5.csv')
APPLY = os.environ.get('FORM5_APPLY') == '1'

COL = {
    'category': 1, 'rank': 2, 'name': 3, 'birth': 4, 'vin': 5, 'rnokpp': 6,
    'vos': 7, 'document': 8, 'passport': 9, 'address': 10, 'tcc': 12,
    # Графа 12 у бланку зазвичай зверстана об'єднаними комірками, і значення
    # опиняється в наступній колонці — тому читаємо обидві.
    'tcc_alt': 13,
    'deferment': 14, 'special': 15, 'service': 16, 'mob': 17,
    'position': 18, 'notice': 19,
}

CATEGORY = {
    'призовник': 'conscript',
    'військовозобов\'язаний': 'liable',
    'військовозобовязаний': 'liable',
    'резервіст': 'reservist',
}

# Звання у бланку — українською, у довіднику модуля — англійською, тож
# зіставляємо через код (стабільніший за назву, яка перекладається).
RANK_CODE = {
    'солдат': 'S01', 'старший солдат': 'S02',
    'молодший сержант': 'N01', 'сержант': 'N02', 'старший сержант': 'N03',
    'головний сержант': 'N04', 'штаб-сержант': 'N05',
    'майстер-сержант': 'N06', 'старший майстер-сержант': 'N07',
    'головний майстер-сержант': 'N08',
    'молодший лейтенант': 'O01', 'лейтенант': 'O02',
    'старший лейтенант': 'O03', 'капітан': 'O04', 'майор': 'O05',
    'підполковник': 'O06', 'полковник': 'O07',
}

DATE_RE = re.compile(r'(\d{2})\.(\d{2})\.(\d{4})')
NEGATIVE = {'', '-', '—', 'ні', 'немає', 'нi'}


# Апостроф у ПІБ трапляється в кількох накресленнях — зводимо всі до прямого,
# інакше «Лук´янчук» і «Лук'янчук» вважаються різними людьми.
APOSTROPHES = str.maketrans({c: "'" for c in "\u2019\u0060\u00b4\u02bc\u2018\u02bb"})


def norm(text):
    return re.sub(r'\s+', ' ', (text or '')).translate(APOSTROPHES).strip()


def parse_date(text):
    """Останню дату в рядку — саме вона зазвичай є датою документа."""
    matches = DATE_RE.findall(text or '')
    if not matches:
        return False
    day, month, year = matches[-1]
    try:
        return datetime(int(year), int(month), int(day)).date()
    except ValueError:
        return False


def name_keys(full_name):
    """Ключі зіставлення від точнішого до слабшого.

    У базі ПІБ записані трьома способами: повністю, «Прізвище І.П.» і
    «Прізвище Ім'я» без по батькові. Тому повертаємо два ключі — прізвище з
    обома ініціалами і прізвище з одним; другий рятує записи без по батькові,
    але вже може дати кілька кандидатів, і тоді запис іде в неоднозначні.
    """
    parts = norm(full_name).lower().replace('.', ' ').split()
    if not parts:
        return []
    surname = parts[0]
    initials = ''.join(part[0] for part in parts[1:3])
    keys = []
    if len(initials) > 1:
        keys.append((surname, initials))
    if initials:
        keys.append((surname, initials[0]))
    return keys or [(surname, '')]


def gender_from_patronymic(full_name):
    """Стать за по батькові — потрібна для III групи Списків (жінки)."""
    parts = norm(full_name).split()
    if len(parts) < 3 or '.' in parts[2]:
        return None
    patronymic = parts[2].lower()
    return 'female' if patronymic.endswith(('вна', 'кызы')) else 'male'


def parse_passport(text):
    """Розібрати графу 10 на серію/номер/ким видано.

    Стара книжечка — дві кириличні літери й шість цифр; ID-картка — дев'ять
    цифр. Усе, що лишилося після номера, — це «ким та коли видано».
    """
    text = norm(text)
    if not text:
        return {}
    old = re.match(r'^([А-ЯІЇЄҐ]{2})\s*№?\s*(\d{5,6})\s*(.*)$', text)
    if old:
        series, number, rest = old.groups()
        return {
            'document_type': 'passport',
            'passport_series': series,
            'passport_id': number,
            'passport_issued_by': norm(re.sub(DATE_RE, '', rest)) or False,
            'passport_issued_date': parse_date(rest),
        }
    new = re.match(r'^№?\s*(\d{9})\s*(.*)$', text)
    if new:
        number, rest = new.groups()
        return {
            'document_type': 'id_card',
            'passport_id': number,
            'passport_issued_by': norm(re.sub(DATE_RE, '', rest)) or False,
            'passport_issued_date': parse_date(rest),
        }
    return {'passport_issued_by': text}


def main():
    Employee = env['hr.employee'].with_context(active_test=False)
    Tcc = env['hr.military.tcc']
    Rank = env['hr.military.rank']

    ranks = {rank.code: rank for rank in Rank.search([])}
    def tcc_key(name):
        """Ключ пошуку ТЦК, стійкий до правопису.

        У бланках назви органів пишуть по-різному: із пропущеним пробілом
        («Рівненськийоб'єднаний»), із хвостовою одруківкою («підтримкм»).
        Ключ лишає самі літери, а решту різниці добирає нечітке зіставлення —
        інакше на кожну одруківку в довіднику з'являється дубль.
        """
        return re.sub(r'[^а-яіїєґa-z]', '', (name or '').lower())

    tcc_cache = {tcc_key(tcc.name): tcc for tcc in Tcc.search([])}

    index = {}
    for employee in Employee.search([]):
        for key in name_keys(employee.name):
            index.setdefault(key, []).append(employee)

    with open(CSV_PATH, encoding='utf-8') as handle:
        rows = [row for row in csv.reader(handle)
                if row and row[0].strip().isdigit()
                and len(row) > COL['name']
                # Рядок нумерації граф («1|2|3|4…») теж починається з цифри,
                # тож рядком даних вважаємо лише той, де в ПІБ є літери.
                and re.search(r'[А-Яа-яІЇЄҐіїєґ]', row[COL['name']])]

    matched, missing, ambiguous, created_tcc = [], [], [], []
    bad_rnokpp = []

    for row in rows:
        def cell(name):
            position = COL[name]
            return norm(row[position]) if len(row) > position else ''

        full_name = cell('name')
        candidates = []
        for key in name_keys(full_name):
            candidates = index.get(key, [])
            if candidates:
                break
        if not candidates:
            missing.append(full_name)
            continue
        if len(candidates) > 1:
            ambiguous.append((full_name, [c.name for c in candidates]))
            continue
        employee = candidates[0]

        values = {}
        category = CATEGORY.get(cell('category').lower())
        if category:
            values['military_register_category'] = category

        rank_code = RANK_CODE.get(cell('rank').lower())
        if rank_code and rank_code in ranks:
            values['military_rank_id'] = ranks[rank_code].id

        if not employee.gender:
            gender = gender_from_patronymic(full_name)
            if gender:
                values['gender'] = gender

        birthday = parse_date(cell('birth'))
        if birthday and not employee.birthday:
            values['birthday'] = birthday

        vin = re.sub(r'\D', '', cell('vin'))
        if vin:
            values['military_vin_code'] = vin

        rnokpp = re.sub(r'\D', '', cell('rnokpp'))
        if len(rnokpp) == 10 and not employee.rnokpp:
            # Модуль перевіряє контрольну суму РНОКПП і блокує запис цілком.
            # Номер із хибною сумою — це майже завжди друкарська помилка в
            # бланку, тож пропускаємо саме його, а не весь рядок.
            if Employee._validate_rnokpp(rnokpp):
                values['rnokpp'] = rnokpp
            else:
                bad_rnokpp.append((full_name, rnokpp))

        if cell('vos'):
            values['military_specialty'] = cell('vos')

        document = cell('document')
        if document:
            values['military_document_number'] = document
            values['military_document_date'] = parse_date(document)
            # Запис, що починається з номера в Реєстрі, — це ВОД в
            # електронній формі; паперові документи мають літерну серію.
            digits_only = re.sub(r'\D', '', document.split()[0]) if document.split() else ''
            values['military_document_type'] = (
                'electronic' if len(digits_only) >= 15
                else 'conscript_card' if category == 'conscript'
                else 'military_card')

        values.update({k: v for k, v in parse_passport(cell('passport')).items() if v})

        address = cell('address')
        if address:
            values['registration_street'] = address

        tcc_name = cell('tcc') or cell('tcc_alt')
        if tcc_name:
            key = tcc_key(tcc_name)
            tcc = tcc_cache.get(key)
            if not tcc:
                near = difflib.get_close_matches(key, tcc_cache, n=1, cutoff=0.93)
                if near:
                    tcc = tcc_cache[near[0]]
            if not tcc:
                tcc = Tcc.create({'name': tcc_name})
                tcc_cache[tcc_key(tcc_name)] = tcc
                created_tcc.append(tcc_name)
            values['military_tcc_id'] = tcc.id

        deferment = cell('deferment')
        if deferment and deferment.lower() not in NEGATIVE:
            values['military_deferment_type'] = (
                'conscript_basic' if category == 'conscript' else 'other')
            values['military_deferment_until'] = parse_date(deferment)

        special = cell('special').lower()
        values['military_reservation'] = special not in NEGATIVE

        service = cell('service')
        if service.lower() not in NEGATIVE:
            values['military_service_status'] = 'serving'
            values['military_service_since'] = parse_date(service)

        mob = cell('mob')
        if mob.lower() not in NEGATIVE:
            values['military_mob_order_number'] = mob
            values['military_mob_order_date'] = parse_date(mob)

        position = cell('position')
        if position:
            # Графа 17 у бланку — це «посада, наказ №… від …» одним рядком.
            # Розділяємо: наказ іде у власне поле, а назва посади — у job_title,
            # бо довідник посад у кадрах часто порожній, і без цього графа
            # друкувалася б без посади.
            order = re.search(r'(наказ.*)$', position, re.IGNORECASE)
            if order:
                values['military_position_order'] = norm(order.group(1))
                job_title = norm(position[:order.start()].rstrip(' ,;'))
            else:
                values['military_position_order'] = position
                job_title = ''
            if job_title and not employee.job_id and not employee.job_title:
                values['job_title'] = job_title[0].upper() + job_title[1:]

        if cell('notice'):
            values['military_notice_ref_manual'] = cell('notice')

        if APPLY:
            employee.write(values)
            # Норма закону — обчислюване поле з ручним редагуванням: пишемо
            # окремо, після типу відстрочки, щоб компʼют не затер текст із бланка.
            if deferment and deferment.lower() not in NEGATIVE:
                employee.military_deferment_basis = deferment
        matched.append((full_name, employee.name, len(values)))

    print('=== ІМПОРТ ДОДАТКА 5 ===')
    print('рядків у файлі:      ', len(rows))
    print('зіставлено:          ', len(matched))
    print('не знайдено в Odoo:  ', len(missing))
    for name in missing:
        print('   —', name)
    print('неоднозначних:       ', len(ambiguous))
    for name, options in ambiguous:
        print('   ?', name, '→', options)
    if bad_rnokpp:
        print('РНОКПП із хибною контрольною сумою (не записані):', len(bad_rnokpp))
        for name, number in bad_rnokpp:
            print('   !', name, number)
    if created_tcc:
        print('створено ТЦК:', len(created_tcc))
        for name in created_tcc:
            print('   +', name)
    print('режим:', 'ЗАПИС' if APPLY else 'сухий прогін (FORM5_APPLY=1 щоб записати)')
    if APPLY:
        env.cr.commit()
        print('зміни збережено')


main()
