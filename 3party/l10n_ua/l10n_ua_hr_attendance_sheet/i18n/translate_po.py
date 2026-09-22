#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_base module."""

import re

TRANSLATIONS = {
    # Common fields
    "Action Needed": "Потрібна дія",
    "Activities": "Активності",
    "Activity Exception Decoration": "Оформлення виключення активності",
    "Activity State": "Стан активності",
    "Activity Type Icon": "Іконка типу активності",
    "Approve": "Затвердити",
    "Approved": "Затверджено",
    "Attachment Count": "Кількість вкладень",
    "Created by": "Створив",
    "Created on": "Створено",
    "Confirm": "Підтвердити",
    "Confirmed": "Підтверджено",
    "Department": "Підрозділ",
    "Display Name": "Відображувана назва",
    "Draft": "Чернетка",
    "Followers": "Підписники",
    "Followers (Partners)": "Підписники (Партнери)",
    "Font awesome icon e.g. fa-tasks": "Іконка Font Awesome, напр. fa-tasks",
    "Has Message": "Є повідомлення",
    "ID": "ID",
    "Icon": "Іконка",
    "Icon to indicate an exception activity.": "Іконка для позначення виключної активності.",
    "If checked, new messages require your attention.": "Якщо позначено, нові повідомлення потребують вашої уваги.",
    "If checked, some messages have a delivery error.": "Якщо позначено, деякі повідомлення мають помилку доставки.",
    "Is Follower": "Є підписником",
    "Last Updated by": "Оновив",
    "Last Updated on": "Оновлено",
    "Message Delivery error": "Помилка доставки повідомлення",
    "Messages": "Повідомлення",
    "My Activity Deadline": "Термін моєї активності",
    "Name": "Назва",
    "Next Activity Calendar Event": "Подія календаря наступної активності",
    "Next Activity Deadline": "Термін наступної активності",
    "Next Activity Summary": "Опис наступної активності",
    "Next Activity Type": "Тип наступної активності",
    "Notes": "Примітки",
    "Number of Actions": "Кількість дій",
    "Number of errors": "Кількість помилок",
    "Number of messages requiring action": "Кількість повідомлень, що потребують дії",
    "Number of messages with delivery error": "Кількість повідомлень з помилкою доставки",
    "Responsible": "Відповідальний",
    "Responsible User": "Відповідальний",
    "SMS Delivery error": "Помилка доставки SMS",
    "Set to Draft": "Повернути в чернетку",
    "Status": "Статус",
    "Type of the exception activity on record.": "Тип виключної активності в записі.",
    "Website Messages": "Повідомлення веб-сайту",
    "Website communication history": "Історія комунікації веб-сайту",
    
    # l10n_ua_hr_attendance_sheet specific
    "Absence": "Відсутність",
    "Absence Days": "Дні відсутності",
    "Active": "Активний",
    "April": "Квітень",
    "August": "Серпень",
    "Calendar": "Календар",
    "Calendar Days": "Календарні дні",
    "Calendar Lines": "Рядки календаря",
    "Code": "Код",
    "Color": "Колір",
    "Company": "Компанія",
    "Configuration": "Налаштування",
    "Counted as Worked": "Зараховується як відпрацьовано",
    "Create a monthly timesheet": "Створити місячний табель",
    "Create a production calendar for the year": "Створити виробничий календар на рік",
    "Date": "Дата",
    "Day": "День",
    "Day Type": "Тип дня",
    "Day of Week": "День тижня",
    "Days": "Дні",
    "December": "Грудень",
    "Default Hours": "Години за замовчуванням",
    "Description": "Опис",
    "Employee": "Працівник",
    "Employees": "Працівники",
    "February": "Лютий",
    "Generate Calendar": "Згенерувати календар",
    "Generate Lines": "Згенерувати рядки",
    "Holiday": "Свято",
    "Holiday Name": "Назва свята",
    "Holidays": "Свята",
    "Hours": "Години",
    "Hours are counted as worked time": "Години зараховуються як відпрацьований час",
    "January": "Січень",
    "Job Position": "Посада",
    "July": "Липень",
    "June": "Червень",
    "Leave": "Відпустка",
    "March": "Березень",
    "May": "Травень",
    "Month": "Місяць",
    "Night Hours": "Нічні години",
    "November": "Листопад",
    "October": "Жовтень",
    "Other": "Інше",
    "Overtime": "Понаднормові",
    "Overtime Hours": "Понаднормові години",
    "Paid": "Оплачуваний",
    "Production Calendar": "Виробничий календар",
    "Production Calendar Line": "Рядок виробничого календаря",
    "Production Calendars": "Виробничі календарі",
    "Production calendar defines working days, weekends, and public holidays.": "Виробничий календар визначає робочі дні, вихідні та державні свята.",
    "Production calendar for this year already exists!": "Виробничий календар на цей рік вже існує!",
    "Production calendar defines working days, weekends, and public holidays.Production calendar defines working days, weekends, and public holidays.": "Виробничий календар визначає робочі дні, вихідні та державні свята.Виробничий календар визначає робочі дні, вихідні та державні свята.",
    "Production calendar defines working days, weekends, and public holidays.Production calendar defines working days, weekends, and public holidays.Production calendar defines working days, weekends, and public holidays.Production calendar defines working days, weekends, and public holidays.": "Виробничий календар визначає робочі дні, вихідні та державні свята.Виробничий календар визначає робочі дні, вихідні та державні свята.Виробничий календар визначає робочі дні, вихідні та державні свята.Виробничий календар визначає робочі дні, вихідні та державні свята.",
    "Public Holiday": "Державне свято",
    "Scheduled": "Заплановано",
    "Scheduled Days": "Заплановані дні",
    "September": "Вересень",
    "Sequence": "Послідовність",
    "Sick Days": "Дні хвороби",
    "Sick Leave": "Лікарняний",
    "Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.": "Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.",
    "Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.": "Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.",
    "Timesheet": "Табель",
    "Timesheet (Form П-5)": "Табель (Форма П-5)",
    "Timesheet Code": "Код табеля",
    "Timesheet Codes": "Коди табеля",
    "Timesheet Day": "День табеля",
    "Timesheet Line": "Рядок табеля",
    "Timesheet Lines": "Рядки табеля",
    "Timesheet code must be unique!": "Код табеля має бути унікальним!",
    "Timesheet for this period already exists!": "Табель за цей період вже існує!",
    "Timesheets": "Табелі",
    "Total": "Всього",
    "Total Days": "Всього днів",
    "Total Employees": "Всього працівників",
    "Total Worked Days": "Всього відпрацьовано днів",
    "Total Worked Hours": "Всього відпрацьовано годин",
    "Transferred Day": "Перенесений день",
    "Type": "Тип",
    "Vacation Days": "Дні відпустки",
    "Weekend": "Вихідний",
    "Work": "Робота",
    "Worked Days": "Відпрацьовано днів",
    "Worked Hours": "Відпрацьовано годин",
    "Working Day": "Робочий день",
    "Working Days": "Робочі дні",
    "Working Hours": "Робочі години",
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
