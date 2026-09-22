#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_base module."""

import re

TRANSLATIONS = {
    # Common
    "Active": "Активний",
    "4DF Report": "Звіт 4ДФ",
    "Acceptance Date": "Дата прийняття",
    "Accepted": "Прийнято",
    "Action Needed": "Потрібна дія",
    "Activities": "Активності",
    "Activity Exception Decoration": "Оформлення виключення активності",
    "Activity State": "Стан активності",
    "Activity Type Icon": "Іконка типу активності",
    "Attachment Count": "Кількість вкладень",
    "Budget Classification Code": "Код бюджетної класифікації",
    "Budget Code": "Код бюджету",
    "Budget classification code for payment": "Код бюджетної класифікації для оплати",
    "Calculate": "Розрахувати",
    "Calculated": "Розраховано",
    "Close": "Закрити",
    "Closed": "Закрито",
    "Code": "Код",
    "Companies": "Компанії",
    "Company": "Компанія",
    "Company Type": "Тип компанії",
    "Created by": "Створено",
    "Created on": "Дата створення",
    "Display Name": "Назва для відображення",
    "Draft": "Чернетка",
    "EP (Single Tax)": "ЄП (Єдиний податок)",
    "ESV": "ЄСВ",
    "ESV (Unified Social Contribution)": "ЄСВ (Єдиний соціальний внесок)",
    "ESV Report": "Звіт ЄСВ",
    "End Date": "Дата закінчення",
    "FOP Group": "Група ФОП",
    "FOP Settings (Single Tax)": "Налаштування ФОП (Єдиний податок)",
    "Followers": "Підписники",
    "Followers (Partners)": "Підписники (Партнери)",
    "Font awesome icon e.g. fa-tasks": "Іконка Font Awesome, напр. fa-tasks",
    "Generate XML": "Згенерувати XML",
    "Group 1": "Група 1",
    "Group 2": "Група 2",
    "Group 3": "Група 3",
    "Has Message": "Має повідомлення",
    "ID": "ID",
    "Icon": "Іконка",
    "Icon to indicate an exception activity.": "Іконка для позначення виключення активності.",
    "If checked, new messages require your attention.": "Якщо позначено, нові повідомлення потребують вашої уваги.",
    "If checked, some messages have a delivery error.": "Якщо позначено, деякі повідомлення мають помилку доставки.",
    "Is FOP": "Є ФОП",
    "Is Follower": "Є підписником",
    "Last Updated by": "Останнє оновлення",
    "Last Updated on": "Дата оновлення",
    "Legal Form": "Організаційно-правова форма",
    "Mark Accepted": "Позначити прийнятим",
    "Message Delivery error": "Помилка доставки повідомлення",
    "Messages": "Повідомлення",
    "Military Tax": "Військовий збір",
    "Month": "Місяць",
    "My Activity Deadline": "Мій дедлайн активності",
    "Name": "Назва",
    "Next Activity Deadline": "Дедлайн наступної активності",
    "Next Activity Summary": "Опис наступної активності",
    "Next Activity Type": "Тип наступної активності",
    "Notes": "Примітки",
    "Notes...": "Примітки...",
    "Number of Actions": "Кількість дій",
    "Number of errors": "Кількість помилок",
    "Number of messages requiring action": "Кількість повідомлень, що потребують дії",
    "Number of messages with delivery error": "Кількість повідомлень з помилкою доставки",
    "Open": "Відкрито",
    "Other": "Інше",
    "PDFO": "ПДФО",
    "PDFO (Personal Income Tax)": "ПДФО (Податок на доходи фізичних осіб)",
    "PDV (VAT)": "ПДВ",
    "Period Type": "Тип періоду",
    "Profit Tax": "Податок на прибуток",
    "Profit Tax Declaration": "Декларація з податку на прибуток",
    "Quarter": "Квартал",
    "Reopen": "Відкрити знову",
    "Report Type": "Тип звіту",
    "Responsible User": "Відповідальний користувач",
    "SMS Delivery error": "Помилка доставки SMS",
    "Set to Draft": "Повернути в чернетку",
    "Single Tax": "Єдиний податок",
    "Single Tax Declaration": "Декларація єдиного податку",
    "Single Tax Rate (%)": "Ставка єдиного податку (%)",
    "Single tax payer group (1, 2, or 3)": "Група платника єдиного податку (1, 2 або 3)",
    "Single tax rate percentage": "Відсоток ставки єдиного податку",
    "Start Date": "Дата початку",
    "State": "Стан",
    "Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.": "Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.",
    "Submission Date": "Дата подання",
    "Submit": "Подати",
    "Submitted": "Подано",
    "Tax": "Податок",
    "Tax Code": "Код податку",
    "Tax Office": "Податкова інспекція",
    "Tax Period": "Податковий період",
    "Tax Periods": "Податкові періоди",
    "Tax Report": "Податковий звіт",
    "Tax Reports": "Податкові звіти",
    "Tax Type": "Тип податку",
    "Tax code for reporting": "Код податку для звітності",
    "Tax office (ДПІ) where the company is registered": "Податкова інспекція (ДПІ), де зареєстрована компанія",
    "Taxes": "Податки",
    "Type of the exception activity on record.": "Тип виключення активності в записі.",
    "UA Tax Type": "Тип податку UA",
    "Ukrainian Tax Settings": "Українські податкові налаштування",
    "VAT": "ПДВ",
    "VAT Declaration": "Декларація з ПДВ",
    "VZ (Military Tax)": "ВЗ (Військовий збір)",
    "Website Messages": "Повідомлення вебсайту",
    "Website communication history": "Історія комунікації вебсайту",
    "XML File": "XML файл",
    "XML Filename": "Назва XML файлу",
    "Year": "Рік",
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
