#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_base module."""

import re

TRANSLATIONS = {
    # Common
    "Active": "Активний",
    "Address": "Адреса",
    "All economic activity codes": "Усі коди економічної діяльності",
    "Apartment": "Квартира",
    "Archived": "Архівовано",
    "BF (Charitable Foundation)": "БФ (Благодійний фонд)",
    "Building": "Будинок",
    "Category": "Категорія",
    "Central": "Центральний",
    "Central Office (ДПС)": "Центральний офіс (ДПС)",
    "Child Offices": "Підпорядковані офіси",
    "Children": "Дочірні",
    "City": "Місто",
    "City/Village": "Місто/Село",
    "Code": "Код",
    "Code (C_STI)": "Код (C_STI)",
    "Community (Hromada)": "Громада",
    "Complete Name": "Повна назва",
    "Contact Information": "Контактна інформація",
    "Create a tax office": "Створити податкову інспекцію",
    "Created by": "Створено",
    "Created on": "Дата створення",
    "DP (State Enterprise)": "ДП (Державне підприємство)",
    "Directories": "Довідники",
    "District": "Район",
    "District (Raion)": "Район",
    "District Code (C_RAJ)": "Код району (C_RAJ)",
    "District Office (ДПІ)": "Районна інспекція (ДПІ)",
    "District code (last 2 digits of C_STI)": "Код району (останні 2 цифри C_STI)",
    "Document Date": "Дата документа",
    "Document Number": "Номер документа",
    "EDRPOU": "ЄДРПОУ",
    "Email": "Електронна пошта",
    "FOP (Individual Entrepreneur)": "ФОП (Фізична особа-підприємець)",
    "Full Address": "Повна адреса",
    "Full tax office code (4 digits), e.g., 2658": "Повний код ДПІ (4 цифри), напр., 2658",
    "GO (Public Organization)": "ГО (Громадська організація)",
    "Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)": "Рівень ієрархії: 1=Секція (A-U), 2=Розділ (01-99), 3=Група (01.1), 4=Клас (01.11)",
    "ID": "ID",
    "IPN/RNOKPP": "ІПН/РНОКПП",
    "Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)": "Індивідуальний податковий номер / Реєстраційний номер облікової картки платника податків (10 або 12 цифр)",
    "Invalid EDRPOU: %s": "Невірний ЄДРПОУ: %s",
    "Invalid IPN/RNOKPP: %s": "Невірний ІПН/РНОКПП: %s",
    "KOATUU": "КОАТУУ",
    "KOATUU/KATOTTG": "КОАТУУ/КАТОТТГ",
    "KOATUU/KATOTTG Directory": "Довідник КОАТУУ/КАТОТТГ",
    "KOATUU/KATOTTG is the Ukrainian classification of administrative-territorial units.": "КОАТУУ/КАТОТТГ — український класифікатор адміністративно-територіальних одиниць.",
    "KP (Communal Enterprise)": "КП (Комунальне підприємство)",
    "KVED": "КВЕД",
    "KVED Codes": "Коди КВЕД",
    "KVED code (e.g., 62.01)": "Код КВЕД (напр., 62.01)",
    "KVED-2010": "КВЕД-2010",
    "KVED-2010 Classifier": "Класифікатор КВЕД-2010",
    "KVED-2010 is the Ukrainian classification of economic activities.": "КВЕД-2010 — український класифікатор видів економічної діяльності.",
    "Last Updated by": "Останнє оновлення",
    "Last Updated on": "Дата оновлення",
    "Legal Form": "Організаційно-правова форма",
    "Level": "Рівень",
    "Name": "Назва",
    "No KOATUU records found": "Записи КОАТУУ не знайдено",
    "No KVED records found": "Записи КВЕД не знайдено",
    "Office Type": "Тип офісу",
    "Other": "Інше",
    "PAT (Public Joint Stock Company)": "ПАТ (Публічне акціонерне товариство)",
    "PP (Private Enterprise)": "ПП (Приватне підприємство)",
    "Parent": "Батьківський",
    "Parent Office": "Головний офіс",
    "Parent Path": "Шлях батьківського",
    "Parent tax office (for district offices)": "Головна ДПІ (для районних інспекцій)",
    "Phone": "Телефон",
    "Postal Code": "Поштовий індекс",
    "PrAT (Private Joint Stock Company)": "ПрАТ (Приватне акціонерне товариство)",
    "Primary KVED": "Основний КВЕД",
    "Primary economic activity code": "Основний код економічної діяльності",
    "Region": "Регіон",
    "Region (Oblast)": "Область",
    "Region Code (C_REG)": "Код регіону (C_REG)",
    "Region code (first 2 digits of C_STI)": "Код регіону (перші 2 цифри C_STI)",
    "Regional": "Регіональний",
    "Regional Office (ГУ ДПС)": "Регіональний офіс (ГУ ДПС)",
    "Section": "Секція",
    "Section letter (A-U)": "Літера секції (A-U)",
    "Settlement from KOATUU/KATOTTG directory": "Населений пункт з довідника КОАТУУ/КАТОТТГ",
    "Short Name": "Коротка назва",
    "Street": "Вулиця",
    "TOV (LLC)": "ТОВ (Товариство з обмеженою відповідальністю)",
    "Tax Office Name": "Назва ДПІ",
    "Tax Offices": "Податкові інспекції",
    "Tax Offices (ДПІ)": "Податкові інспекції (ДПІ)",
    "Town": "Селище міського типу",
    "Ukraine": "Україна",
    "Ukrainian Address Mixin": "Міксин української адреси",
    "Ukrainian Document Mixin": "Міксин українського документа",
    "Ukrainian region (oblast)": "Українська область",
    "Ukrainian tax offices (ДПІ) directory.": "Довідник податкових інспекцій (ДПІ) України.",
    "Unified State Register of Enterprises and Organizations of Ukraine (8 digits)": "Єдиний державний реєстр підприємств та організацій України (8 цифр)",
    "Urban Settlement": "Селище міського типу",
    "VAT Certificate Number": "Номер свідоцтва ПДВ",
    "VAT Payer": "Платник ПДВ",
    "VAT Payers": "Платники ПДВ",
    "Village": "Село",
    "Village/Settlement": "Село/Селище",
    # Duplicated strings (PO export issue)
    "Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)": "Рівень ієрархії: 1=Секція (A-U), 2=Розділ (01-99), 3=Група (01.1), 4=Клас (01.11)",
    "Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)Hierarchy level: 1=Section (A-U), 2=Division (01-99), 3=Group (01.1), 4=Class (01.11)": "Рівень ієрархії: 1=Секція (A-U), 2=Розділ (01-99), 3=Група (01.1), 4=Клас (01.11)",
    "Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)": "Індивідуальний податковий номер / Реєстраційний номер облікової картки платника податків (10 або 12 цифр)",
    "Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)Individual Tax Number / Registration Number of the Taxpayer Account Card (10 or 12 digits)": "Індивідуальний податковий номер / Реєстраційний номер облікової картки платника податків (10 або 12 цифр)",
    "KOATUU/KATOTTG is the Ukrainian classification of administrative-territorial units.KOATUU/KATOTTG is the Ukrainian classification of administrative-territorial units.": "КОАТУУ/КАТОТТГ — український класифікатор адміністративно-територіальних одиниць.",
    "KOATUU/KATOTTG is the Ukrainian classification of administrative-territorial units.KOATUU/KATOTTG is the Ukrainian classification of administrative-territorial units.KOATUU/KATOTTG is the Ukrainian classification of administrative-territorial units.KOATUU/KATOTTG is the Ukrainian classification of administrative-territorial units.": "КОАТУУ/КАТОТТГ — український класифікатор адміністративно-територіальних одиниць.",
    "Unified State Register of Enterprises and Organizations of Ukraine (8 digits)Unified State Register of Enterprises and Organizations of Ukraine (8 digits)": "Єдиний державний реєстр підприємств та організацій України (8 цифр)",
    "Unified State Register of Enterprises and Organizations of Ukraine (8 digits)Unified State Register of Enterprises and Organizations of Ukraine (8 digits)Unified State Register of Enterprises and Organizations of Ukraine (8 digits)Unified State Register of Enterprises and Organizations of Ukraine (8 digits)": "Єдиний державний реєстр підприємств та організацій України (8 цифр)",
}


def is_english(text):
    """Check if text is primarily English (ASCII letters)."""
    if not text:
        return False
    ascii_letters = sum(1 for c in text if c.isascii() and c.isalpha())
    total_letters = sum(1 for c in text if c.isalpha())
    if total_letters == 0:
        return False
    return ascii_letters / total_letters > 0.8


def translate_po(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    result = []
    i = 0
    translated_count = 0
    untranslated = []

    while i < len(lines):
        line = lines[i]
        result.append(line)

        # Handle msgid (both single-line and multi-line)
        if line.startswith('msgid "'):
            if line == 'msgid ""':
                # Multi-line msgid starting with empty string
                msgid = ""
                j = i + 1
                while j < len(lines) and lines[j].startswith('"'):
                    msgid += lines[j][1:-1]
                    result.append(lines[j])
                    j += 1
            else:
                # Single-line or continuation msgid
                msgid = line[7:-1]
                j = i + 1
                while j < len(lines) and lines[j].startswith('"'):
                    msgid += lines[j][1:-1]
                    result.append(lines[j])
                    j += 1

            # Check if msgstr is empty and we have a translation
            if j < len(lines) and lines[j].startswith('msgstr "'):
                msgstr_line = lines[j]
                # Check if msgstr is empty (either 'msgstr ""' alone or followed by empty continuations)
                if msgstr_line == 'msgstr ""':
                    # Check if next lines are empty string continuations
                    k = j + 1
                    msgstr_empty = True
                    while k < len(lines) and lines[k].startswith('"'):
                        if lines[k] != '""':
                            msgstr_empty = False
                            break
                        k += 1

                    if msgstr_empty and msgid and msgid in TRANSLATIONS:
                        translation = TRANSLATIONS[msgid]
                        # Handle multi-line translations
                        if '\n' in translation:
                            result.append('msgstr ""')
                            for part in translation.split('\n'):
                                result.append(f'"{part}\\n"')
                            # Remove trailing \n from last part
                            if result[-1].endswith('\\n"'):
                                result[-1] = result[-1][:-3] + '"'
                        else:
                            result.append(f'msgstr "{translation}"')
                        translated_count += 1
                        i = j + 1
                        continue
                    elif msgstr_empty and msgid and is_english(msgid) and msgid not in TRANSLATIONS:
                        untranslated.append(msgid)

        i += 1

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(result))

    print(f"Translated {translated_count} strings")

    if untranslated:
        print(f"\nUntranslated English strings ({len(untranslated)}):")
        for s in sorted(set(untranslated)):
            print(f'    "{repr(s)[1:-1]}": "",')


if __name__ == '__main__':
    translate_po('uk_UA.po', 'uk_UA.po')
