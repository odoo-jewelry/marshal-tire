#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_documents_certificates module."""

TRANSLATIONS = {
    # Certificate Model
    "HR Certificate": "Довідка",
    "HR Certificate Type": "Тип довідки",
    "Certificate": "Довідка",
    "Certificates": "Довідки",
    "Certificates Count": "Кількість довідок",
    "Certificate Type": "Тип довідки",
    "Certificate Type Name": "Назва типу довідки",
    "Certificate Types": "Типи довідок",
    "Certificate Body": "Тіло довідки",
    "Certificate Content": "Зміст довідки",
    "Certificate content. Loaded from template, can be edited.": "Зміст довідки. Завантажується з шаблону, можна редагувати.",
    "Create your first certificate type": "Створіть перший тип довідки",
    "Issue a new certificate": "Видати нову довідку",

    # Certificate Fields
    "Number": "Номер",
    "Request Date": "Дата запиту",
    "Issue Date": "Дата видачі",
    "Issued By": "Ким видано",
    "Valid Until": "Дійсний до",
    "Validity (days)": "Термін дії (дні)",
    "Number of days the certificate is valid": "Кількість днів дії довідки",
    "Number of Copies": "Кількість копій",
    "Destination": "Призначення",
    "Where the certificate will be presented": "Куди буде подано довідку",

    # Certificate Requirements
    "Requires Destination": "Потребує призначення",
    "Requires Period": "Потребує період",
    "Requires Salary Information": "Потребує інформацію про зарплату",
    "If checked, destination field is required": "Якщо позначено, поле призначення є обов'язковим",
    "If checked, period dates are required": "Якщо позначено, дати періоду є обов'язковими",
    "If checked, salary data will be included": "Якщо позначено, дані про зарплату будуть включені",

    # Period & Salary
    "Period From": "Період з",
    "Period To": "Період до",
    "Current Salary": "Поточний оклад",
    "Total Income (Period)": "Загальний дохід (за період)",
    "Total income for the specified period": "Загальний дохід за вказаний період",
    "Currency": "Валюта",

    # Template
    "Template": "Шаблон",
    "Template Body": "Тіло шаблону",
    "Report Template": "Шаблон звіту",
    "Custom report template for this certificate type": "Власний шаблон звіту для цього типу довідки",

    # Sequence
    "Document Sequence": "Послідовність документів",
    "Sequence used for numbering certificates of this type": "Послідовність для нумерації довідок цього типу",

    # Status & States
    "Status": "Статус",
    "Draft": "Чернетка",
    "Approved": "Затверджено",
    "Issued": "Видано",
    "Cancelled": "Скасовано",
    "Active": "Активний",
    "Archived": "Архівовано",

    # Actions
    "Approve": "Затвердити",
    "Issue": "Видати",
    "Print": "Друк",
    "Cancel": "Скасувати",
    "Reload Template": "Перезавантажити шаблон",
    "Set to Draft": "Повернути в чернетку",

    # Common Fields
    "Name": "Назва",
    "Code": "Код",
    "Description": "Опис",
    "Notes": "Примітки",
    "Internal Notes": "Внутрішні примітки",
    "Internal notes...": "Внутрішні примітки...",
    "Sequence": "Послідовність",
    "Company": "Компанія",
    "Employee": "Працівник",

    # Multi-line strings
    "Certificate types define templates for standard HR documents like\n                employment certificates, salary certificates, etc.": "Типи довідок визначають шаблони для стандартних кадрових документів,\n                таких як довідки про роботу, довідки про зарплату тощо.",
    "Create certificates for employees: employment certificates,\n                salary certificates, income references, and more.": "Створюйте довідки для працівників: довідки про роботу,\n                довідки про зарплату, довідки про доходи тощо.",

    # Messages & Activity (standard Odoo)
    "Action Needed": "Потрібна дія",
    "Activities": "Активності",
    "Activity Exception Decoration": "Оформлення виключення активності",
    "Activity State": "Стан активності",
    "Activity Type Icon": "Іконка типу активності",
    "Attachment Count": "Кількість вкладень",
    "Created by": "Створив",
    "Created on": "Створено",
    "Display Name": "Відображуване ім'я",
    "Followers": "Підписники",
    "Followers (Partners)": "Підписники (Партнери)",
    "Font awesome icon e.g. fa-tasks": "Іконка Font Awesome, напр. fa-tasks",
    "Has Message": "Має повідомлення",
    "Icon": "Іконка",
    "Icon to indicate an exception activity.": "Іконка для позначення виключної активності.",
    "ID": "ID",
    "If checked, new messages require your attention.": "Якщо позначено, нові повідомлення потребують вашої уваги.",
    "If checked, some messages have a delivery error.": "Якщо позначено, деякі повідомлення мають помилку доставки.",
    "Is Follower": "Є підписником",
    "Last Updated by": "Оновив",
    "Last Updated on": "Оновлено",
    "Message Delivery error": "Помилка доставки повідомлення",
    "Messages": "Повідомлення",
    "My Activity Deadline": "Термін моєї активності",
    "Next Activity Calendar Event": "Подія календаря наступної активності",
    "Next Activity Deadline": "Термін наступної активності",
    "Next Activity Summary": "Опис наступної активності",
    "Next Activity Type": "Тип наступної активності",
    "Number of Actions": "Кількість дій",
    "Number of errors": "Кількість помилок",
    "Number of messages requiring action": "Кількість повідомлень, що потребують дії",
    "Number of messages with delivery error": "Кількість повідомлень з помилкою доставки",
    "Responsible User": "Відповідальний",
    "SMS Delivery error": "Помилка доставки SMS",
    "Type of the exception activity on record.": "Тип виключної активності в записі.",
    "Website communication history": "Історія комунікації веб-сайту",
    "Website Messages": "Повідомлення веб-сайту",
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
                        i = k
                        continue
                    elif msgstr_empty and msgid and is_english(msgid) and msgid not in TRANSLATIONS:
                        untranslated.append(msgid)
            # The msgid continuation lines were already copied above. Resume at
            # the msgstr line so the outer loop does not copy them a second
            # time — doing so duplicated them on every run and produced msgids
            # that no source string can ever match.
            i = j
            continue

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
