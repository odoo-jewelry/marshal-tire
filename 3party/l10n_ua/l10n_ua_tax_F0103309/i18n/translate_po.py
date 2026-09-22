#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_base module."""

import re

TRANSLATIONS = {
    # Common
    "Active": "Активний",
    "Activity Codes": "Коди діяльності",
    "Activity Codes (KVED)": "Коди діяльності (КВЕД)",
    "Clarifying": "Уточнююча",
    "Code": "Код",
    "Created by": "Створено",
    "Created on": "Дата створення",
    "Declaration Settings": "Налаштування декларації",
    "Declaration Type": "Тип декларації",
    "ESV (Section 8)": "ЄСВ (Розділ 8)",
    "ESV Amount": "Сума ЄСВ",
    "ESV Base": "База ЄСВ",
    "ESV Rate (%)": "Ставка ЄСВ (%)",
    "Employee Count": "Кількість працівників",
    "FOP Group": "Група ФОП",
    "Group 1": "Група 1",
    "Group 2": "Група 2",
    "Group 3": "Група 3",
    "Has Employees": "Має працівників",
    "ID": "ID",
    "Income by Quarter (Section 5)": "Дохід по кварталах (Розділ 5)",
    "KVED": "КВЕД",
    "KVED code (e.g., 62.01)": "Код КВЕД (напр., 62.01)",
    "Last Updated by": "Останнє оновлення",
    "Last Updated on": "Дата оновлення",
    "Name": "Назва",
    "New Reporting": "Нова звітна",
    "Primary": "Основний",
    "Q1 Income": "Дохід К1",
    "Q1 Tax": "Податок К1",
    "Q2 Income": "Дохід К2",
    "Q2 Tax": "Податок К2",
    "Q3 Income": "Дохід К3",
    "Q3 Tax": "Податок К3",
    "Q4 Income": "Дохід К4",
    "Q4 Tax": "Податок К4",
    "Reporting": "Звітна",
    "Single Tax Declaration (F0103309)": "Декларація єдиного податку (F0103309)",
    "Single tax rate: 5% for Group 3 (standard), 2% for e-residents, etc.": "Ставка єдиного податку: 5% для Групи 3 (стандартна), 2% для е-резидентів тощо.",
    "Tax Document Data Wizard": "Майстер даних податкового документа",
    "Tax Document Wizard Activity Code": "Код діяльності майстра податкового документа",
    "Tax Office": "Податкова інспекція",
    "Tax Rate (%)": "Ставка податку (%)",
    "Total Income": "Загальний дохід",
    "Total Tax": "Загальний податок",
    "Wizard": "Майстер",
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
