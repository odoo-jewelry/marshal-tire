#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_base module."""

import re

TRANSLATIONS = {
    # Common fields
    "Action Needed": "Потрібна дія",
    "Activate": "Активувати",
    "Active": "Активний",
    "Activities": "Активності",
    "Activity Exception Decoration": "Оформлення виключення активності",
    "Activity State": "Стан активності",
    "Activity Type Icon": "Іконка типу активності",
    "Attachment Count": "Кількість вкладень",
    "Cancel": "Скасувати",
    "Cancelled": "Скасовано",
    "Close": "Закрити",
    "Closed": "Закрито",
    "Code": "Код",
    "Company": "Компанія",
    "Configuration": "Налаштування",
    "Confirm": "Підтвердити",
    "Contract": "Контракт",
    "Created by": "Створив",
    "Created on": "Створено",
    "Currency": "Валюта",
    "Department": "Підрозділ",
    "Description": "Опис",
    "Display Name": "Відображувана назва",
    "Done": "Виконано",
    "Draft": "Чернетка",
    "Employee": "Працівник",
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
    "Job Position": "Посада",
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
    "None": "Немає",
    "Notes": "Примітки",
    "Number of Actions": "Кількість дій",
    "Number of errors": "Кількість помилок",
    "Number of messages requiring action": "Кількість повідомлень, що потребують дії",
    "Number of messages with delivery error": "Кількість повідомлень з помилкою доставки",
    "Other": "Інше",
    "Period": "Період",
    "Print": "Друк",
    "Priority": "Пріоритет",
    "Quantity": "Кількість",
    "Rate": "Ставка",
    "Reference": "Номер",
    "Responsible User": "Відповідальний",
    "SMS Delivery error": "Помилка доставки SMS",
    "Sequence": "Послідовність",
    "Set to Draft": "Повернути в чернетку",
    "Status": "Статус",
    "Summary": "Підсумок",
    "Suspend": "Призупинити",
    "Suspended": "Призупинено",
    "Total": "Всього",
    "Type of the exception activity on record.": "Тип виключної активності в записі.",
    "Verify": "Перевірити",
    "Waiting": "Очікування",
    "Website Messages": "Повідомлення веб-сайту",
    "Website communication history": "Історія комунікації веб-сайту",
    "Year": "Рік",
    
    # l10n_ua_hr_salary specific
    "4DF Income Type": "Тип доходу 4ДФ",
    "4DF Income Type Code": "Код типу доходу 4ДФ",
    "Accounting": "Бухгалтерія",
    "Accrual Type": "Тип нарахування",
    "Accrual Types": "Типи нарахувань",
    "Accrual type code must be unique!": "Код типу нарахування має бути унікальним!",
    "Accruals": "Нарахування",
    "Advance Deduction": "Утримання авансу",
    "Alimony": "Аліменти",
    "Allowance": "Надбавка",
    "Amount": "Сума",
    "Amount used as calculation base": "Сума, що використовується як база розрахунку",
    "Automatically applied to all payslips": "Автоматично застосовується до всіх розрахункових листків",
    "Base Amount": "Базова сума",
    "Base Values": "Базові значення",
    "Base Wage": "Базова зарплата",
    "Basic Salary Component": "Компонент основної зарплати",
    "Batches": "Пакети",
    "Bonus": "Премія",
    "Calculation": "Розрахунок",
    "Calculation Method": "Метод розрахунку",
    "Category": "Категорія",
    "Collected Amount": "Зібрана сума",
    "Compensation": "Компенсація",
    "Compute All": "Розрахувати все",
    "Compute Sheet": "Розрахувати листок",
    "Configure PSP parameters for each period": "Налаштуйте параметри ПСП для кожного періоду",
    "Court Decision": "Рішення суду",
    "Create a payslip batch to process multiple payslips at once": "Створіть пакет розрахункових листків для обробки кількох листків одночасно",
    "Create an execution document": "Створіть виконавчий документ",
    "Create your first payslip": "Створіть свій перший розрахунковий листок",
    "Credit Account": "Кредитовий рахунок",
    "Daily Rate": "Денна ставка",
    "Damage Compensation": "Компенсація збитків",
    "Date From": "Дата з",
    "Date To": "Дата по",
    "Days, hours, or units": "Дні, години або одиниці",
    "Debit Account": "Дебетовий рахунок",
    "Deduction Priority": "Пріоритет утримання",
    "Deduction Type": "Тип утримання",
    "Deduction Types": "Типи утримань",
    "Deduction priority (lower = first). Alimony has priority 1-3.": "Пріоритет утримання (менше = перше). Аліменти мають пріоритет 1-3.",
    "Deduction type code must be unique!": "Код типу утримання має бути унікальним!",
    "Deductions": "Утримання",
    "Default Amount": "Сума за замовчуванням",
    "Default Rate (%)": "Ставка за замовчуванням (%)",
    "Document Number": "Номер документа",
    "Document Type": "Тип документа",
    "ESV (Employer Cost)": "ЄСВ (витрати роботодавця)",
    "ESV (Employer)": "ЄСВ (роботодавець)",
    "ESV Amount": "Сума ЄСВ",
    "ESV Base": "База ЄСВ",
    "ESV Rate (%)": "Ставка ЄСВ (%)",
    "Execution Document": "Виконавчий документ",
    "Execution Documents": "Виконавчі документи",
    "Execution documents are used for automatic deductions like alimony,\\n                court decisions, and other mandatory payments.": "Виконавчі документи використовуються для автоматичних утримань, таких як аліменти,\\n                рішення суду та інші обов'язкові платежі.",
    "Expense account": "Рахунок витрат",
    "First Priority (Alimony for minors)": "Перша черга (аліменти на неповнолітніх)",
    "Fixed Amount": "Фіксована сума",
    "Generate Payslips": "Згенерувати розрахункові листки",
    "Gross Salary": "Нарахована зарплата",
    "Hourly Rate": "Погодинна ставка",
    "Include in average salary calculation": "Включити в розрахунок середньої зарплати",
    "Income Limit for PSP": "Ліміт доходу для ПСП",
    "Income type code for 4DF report": "Код типу доходу для звіту 4ДФ",
    "Liability account": "Рахунок зобов'язань",
    "Loan Repayment": "Погашення позики",
    "Mandatory": "Обов'язковий",
    "Maternity Leave": "Декретна відпустка",
    "Max Deduction (%)": "Макс. утримання (%)",
    "Max ESV Base": "Макс. база ЄСВ",
    "Max Percent of Salary": "Макс. відсоток від зарплати",
    "Maximum percent of salary that can be deducted (50% or 70% for alimony)": "Максимальний відсоток зарплати, який можна утримати (50% або 70% для аліментів)",
    "Maximum percent that can be deducted (50% or 70% for alimony)": "Максимальний відсоток, який можна утримати (50% або 70% для аліментів)",
    "Military Tax": "Військовий збір",
    "Military Tax Amount": "Сума військового збору",
    "Military Tax Base": "База військового збору",
    "Military Tax Rate (%)": "Ставка військового збору (%)",
    "Minimum Wage": "Мінімальна зарплата",
    "Monthly Salary": "Місячна зарплата",
    "Net Salary": "Зарплата до виплати",
    "Other Debt": "Інший борг",
    "Other Deductions": "Інші утримання",
    "PDFO": "ПДФО",
    "PDFO Amount": "Сума ПДФО",
    "PDFO Base": "База ПДФО",
    "PDFO Rate (%)": "Ставка ПДФО (%)",
    "PSP (Tax Social Benefit)": "ПСП (Податкова соціальна пільга)",
    "PSP 150%": "ПСП 150%",
    "PSP 200%": "ПСП 200%",
    "PSP Amount": "Сума ПСП",
    "PSP Amounts (Computed)": "Суми ПСП (розраховані)",
    "PSP Eligible": "Право на ПСП",
    "PSP Parameters": "Параметри ПСП",
    "PSP Standard (50%)": "ПСП стандартна (50%)",
    "PSP Type": "Тип ПСП",
    "Parameters for this period already exist!": "Параметри для цього періоду вже існують!",
    "Payroll": "Зарплата",
    "Payslip": "Розрахунковий листок",
    "Payslip Accrual": "Нарахування розрахункового листка",
    "Payslip Batch": "Пакет розрахункових листків",
    "Payslip Batches": "Пакети розрахункових листків",
    "Payslip Count": "Кількість розрахункових листків",
    "Payslip Deduction": "Утримання розрахункового листка",
    "Payslips": "Розрахункові листки",
    "Percent (%)": "Відсоток (%)",
    "Percent of Base": "Відсоток від бази",
    "Percent of Gross": "Відсоток від нарахованого",
    "Percent of Income": "Відсоток від доходу",
    "Percent of Minimum Wage": "Відсоток від мінімальної зарплати",
    "Percent of Net": "Відсоток від чистого",
    "Percent of Tax Base": "Відсоток від податкової бази",
    "Rate (%)": "Ставка (%)",
    "Rate per unit (hourly/daily rate)": "Ставка за одиницю (погодинна/денна)",
    "Recipient": "Отримувач",
    "Recipient Account (IBAN)": "Рахунок отримувача (IBAN)",
    "Recipient Bank": "Банк отримувача",
    "Recipient Name": "Ім'я отримувача",
    "Recipient RNOKPP": "РНОКПП отримувача",
    "Registration Number of the Taxpayer Account Card (Individual Tax Number)": "Реєстраційний номер облікової картки платника податків (ІПН)",
    "Remaining Amount": "Залишок суми",
    "RNOKPP": "РНОКПП",
    "Scheduled": "Заплановано",
    "Scheduled Days": "Заплановані дні",
    "Scheduled Hours": "Заплановані години",
    "Second Priority (Other alimony)": "Друга черга (інші аліменти)",
    "Sick Leave": "Лікарняний",
    "Social Contribution": "Соціальний внесок",
    "Standard (50%)": "Стандартна (50%)",
    "Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.": "Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.",
    "Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.": "Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.",
    "Execution documents are used for automatic deductions like alimony,\\n                court decisions, and other mandatory payments.Execution documents are used for automatic deductions like alimony,\\n                court decisions, and other mandatory payments.": "Виконавчі документи використовуються для автоматичних утримань, таких як аліменти,\\n                рішення суду та інші обов'язкові платежі.Виконавчі документи використовуються для автоматичних утримань, таких як аліменти,\\n                рішення суду та інші обов'язкові платежі.",
    "Maximum percent of salary that can be deducted (50% or 70% for alimony)Maximum percent of salary that can be deducted (50% or 70% for alimony)": "Максимальний відсоток зарплати, який можна утримати (50% або 70% для аліментів)Максимальний відсоток зарплати, який можна утримати (50% або 70% для аліментів)",
    "Registration Number of the Taxpayer Account Card (Individual Tax Number)Registration Number of the Taxpayer Account Card (Individual Tax Number)": "Реєстраційний номер облікової картки платника податків (ІПН)Реєстраційний номер облікової картки платника податків (ІПН)",
    "Subsistence Minimum": "Прожитковий мінімум",
    "Tax": "Податок",
    "Tax Debt": "Податковий борг",
    "Tax Rates": "Податкові ставки",
    "Taxable (PDFO)": "Оподатковується (ПДФО)",
    "Taxes & Deductions": "Податки та утримання",
    "Third Priority (Other debts)": "Третя черга (інші борги)",
    "Total Amount to Collect": "Загальна сума до стягнення",
    "Total Deductions": "Всього утримань",
    "Total ESV": "Всього ЄСВ",
    "Total Gross": "Всього нараховано",
    "Total Military": "Всього військового збору",
    "Total Military Tax": "Всього військового збору",
    "Total Net": "Всього до виплати",
    "Total PDFO": "Всього ПДФО",
    "Union Fees": "Профспілкові внески",
    "Vacation Pay": "Відпускні",
    "Worked": "Відпрацьовано",
    "Worked Days": "Відпрацьовано днів",
    "Worked Hours": "Відпрацьовано годин",
    "Worked Time": "Відпрацьований час",
    "Working days in period according to calendar": "Робочі дні в періоді згідно з календарем",
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
