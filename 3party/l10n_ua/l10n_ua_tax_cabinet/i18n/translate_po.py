#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_base module."""

import re

TRANSLATIONS = {
    # Common
    "Activities": "Активності",
    "/opt/iit/certificates": "/opt/iit/certificates",
    "/opt/iit/eu/sw": "/opt/iit/eu/sw",
    "/path/to/key.dat": "/path/to/key.dat",
    "<em>Note: This token expires and needs to be refreshed manually.</em>": "<em>Примітка: Цей токен закінчується і потребує ручного оновлення.</em>",
    "<span class=\"o_stat_text\">Documents</span>": "<span class=\"o_stat_text\">Документи</span>",
    "<span class=\"o_stat_text\">Signed</span>": "<span class=\"o_stat_text\">Підписано</span>",
    "<strong>Authentication:</strong> Uses KEP (qualified electronic signature) configured in the Tax Cabinet connection.": "<strong>Автентифікація:</strong> Використовує КЕП (кваліфікований електронний підпис), налаштований у підключенні до Податкового кабінету.",
    "<strong>KEP Authentication Setup:</strong>": "<strong>Налаштування автентифікації КЕП:</strong>",
    "<strong>Manual Token Authentication:</strong>": "<strong>Ручна автентифікація токеном:</strong>",
    "API error %s: %s": "Помилка API %s: %s",
    "Accepted": "Прийнято",
    "Action Needed": "Потрібна дія",
    "Active": "Активний",
    "Activity Codes (KVED)": "Коди діяльності (КВЕД)",
    "Activity Exception Decoration": "Оформлення виключення активності",
    "Activity State": "Стан активності",
    "Activity Type Icon": "Іконка типу активності",
    "Additional notes...": "Додаткові примітки...",
    "Address": "Адреса",
    "Adjustment Calculation": "Розрахунок коригування",
    "April": "Квітень",
    "Archived": "Архівовано",
    "Attachment Count": "Кількість вкладень",
    "August": "Серпень",
    "Auth Method": "Метод автентифікації",
    "Auth Token": "Токен автентифікації",
    "Authentication": "Автентифікація",
    "Auto Download PDF": "Автозавантаження PDF",
    "Auto Download XML": "Автозавантаження XML",
    "Automatically download PDF version of documents": "Автоматично завантажувати PDF версію документів",
    "Automatically download XML version of documents": "Автоматично завантажувати XML версію документів",
    "Cabinet Connections": "Підключення до кабінету",
    "Cancel": "Скасувати",
    "Cannot delete accepted document '%s'.": "Неможливо видалити прийнятий документ '%s'.",
    "Cannot modify accepted document '%s'. Accepted documents are read-only.": "Неможливо змінити прийнятий документ '%s'. Прийняті документи доступні лише для читання.",
    "Category": "Категорія",
    "Code": "Код",
    "Company": "Компанія",
    "Company Activity Code (KVED)": "Код діяльності компанії (КВЕД)",
    "Configuration": "Налаштування",
    "Configure connection to cabinet.tax.gov.ua for syncing tax documents using KEP (qualified electronic signature).": "Налаштуйте підключення до cabinet.tax.gov.ua для синхронізації податкових документів за допомогою КЕП (кваліфікованого електронного підпису).",
    "Confirmation of document acceptance": "Підтвердження прийняття документа",
    "Confirmation of document registration": "Підтвердження реєстрації документа",
    "Connection failed: %s": "Помилка підключення: %s",
    "Connection successful! Taxpayer: %s": "Підключення успішне! Платник податків: %s",
    "Create your first Tax Cabinet connection": "Створіть перше підключення до Податкового кабінету",
    "Created by": "Створено",
    "Created on": "Дата створення",
    "DPS encryption certificate not found in %s": "Сертифікат шифрування ДПС не знайдено в %s",
    "Date when document was synced from external system": "Дата синхронізації документа із зовнішньої системи",
    "December": "Грудень",
    "Declaration": "Декларація",
    "Description": "Опис",
    "Document": "Документ",
    "Document Date": "Дата документа",
    "Document ID from external system": "ID документа із зовнішньої системи",
    "Document Info": "Інформація про документ",
    "Document Name": "Назва документа",
    "Document Number": "Номер документа",
    "Document Type": "Тип документа",
    "Document Type Code": "Код типу документа",
    "Document Types": "Типи документів",
    "Document name": "Назва документа",
    "Document signed successfully! Download the signed file.": "Документ успішно підписано! Завантажте підписаний файл.",
    "Document submitted to cabinet.tax.gov.ua!": "Документ подано до cabinet.tax.gov.ua!",
    "Document type '%s' is not supported yet. Please install the corresponding module (l10n_ua_tax_%s).": "Тип документа '%s' ще не підтримується. Будь ласка, встановіть відповідний модуль (l10n_ua_tax_%s).",
    "Draft": "Чернетка",
    "EDRPOU (for companies) or RNOKPP (for FOP)": "ЄДРПОУ (для компаній) або РНОКПП (для ФОП)",
    "EDRPOU or RNOKPP": "ЄДРПОУ або РНОКПП",
    "Email": "Електронна пошта",
    "Enter the password for your private key": "Введіть пароль для вашого приватного ключа",
    "Enter the path to your private key file (.dat, .jks, .pfx)": "Введіть шлях до файлу приватного ключа (.dat, .jks, .pfx)",
    "Error:": "Помилка:",
    "External ID": "Зовнішній ID",
    "FREDO": "FREDO",
    "February": "Лютий",
    "File": "Файл",
    "Filename": "Назва файлу",
    "Files": "Файли",
    "Fill Data": "Заповнити дані",
    "Fill Document Data": "Заповнити дані документа",
    "Followers": "Підписники",
    "Followers (Partners)": "Підписники (Партнери)",
    "Font awesome icon e.g. fa-tasks": "Іконка Font Awesome, напр. fa-tasks",
    "Generate XML": "Згенерувати XML",
    "H1": "П1",
    "H2": "П2",
    "Has Message": "Має повідомлення",
    "ID": "ID",
    "IIT Certificates Path": "Шлях до сертифікатів ІІТ",
    "IIT Library Path": "Шлях до бібліотеки ІІТ",
    "Icon": "Іконка",
    "Icon to indicate an exception activity.": "Іконка для позначення виключення активності.",
    "If checked, new messages require your attention.": "Якщо позначено, нові повідомлення потребують вашої уваги.",
    "If checked, some messages have a delivery error.": "Якщо позначено, деякі повідомлення мають помилку доставки.",
    "Income Tax Declaration": "Декларація про доходи",
    "Incoming Correspondence": "Вхідна кореспонденція",
    "Install IIT library: <code>sudo dpkg -i euswi.64.deb</code> (download from": "Встановіть бібліотеку ІІТ: <code>sudo dpkg -i euswi.64.deb</code> (завантажте з",
    "Is Follower": "Є підписником",
    "January": "Січень",
    "July": "Липень",
    "June": "Червень",
    "KEP (Private Key)": "КЕП (Приватний ключ)",
    "KEP Key File": "Файл ключа КЕП",
    "KEP Password": "Пароль КЕП",
    "KEP Settings": "Налаштування КЕП",
    "KEP authentication not configured.\\n\\nPlease configure in the Tax Cabinet connection:\\n1. KEP Key File path (.dat, .jks, .pfx)\\n2. KEP Password\\n3. IIT Library and Certificates paths": "Автентифікація КЕП не налаштована.\\n\\nБудь ласка, налаштуйте в підключенні до Податкового кабінету:\\n1. Шлях до файлу ключа КЕП (.dat, .jks, .pfx)\\n2. Пароль КЕП\\n3. Шляхи до бібліотеки та сертифікатів ІІТ",
    "KEP key file and password are required for KEP authentication.": "Файл ключа КЕП та пароль необхідні для автентифікації КЕП.",
    "KEP key file and password are required for signing.": "Файл ключа КЕП та пароль необхідні для підписання.",
    "KEP key file and password are required for submission.": "Файл ключа КЕП та пароль необхідні для подання.",
    "KEP key file not found: %s": "Файл ключа КЕП не знайдено: %s",
    "KEP signing failed: %s": "Помилка підписання КЕП: %s",
    "KEP signing library not available: %s": "Бібліотека підписання КЕП недоступна: %s",
    "KEP-signed document ready for submission": "Документ, підписаний КЕП, готовий до подання",
    "KVED": "КВЕД",
    "KVED code (e.g., 62.01)": "Код КВЕД (напр., 62.01)",
    "Last Sync": "Остання синхронізація",
    "Last Updated by": "Останнє оновлення",
    "Last Updated on": "Дата оновлення",
    "Leave empty to extract from file": "Залиште порожнім для витягування з файлу",
    "Loading...": "Завантаження...",
    "M.E.Doc": "M.E.Doc",
    "MIIStwYJKoZIhvcNAQ...": "MIIStwYJKoZIhvcNAQ...",
    "Make sure KEP key file and password are set in the configuration before syncing.": "Переконайтеся, що файл ключа КЕП та пароль встановлені в налаштуваннях перед синхронізацією.",
    "Manual Token": "Ручний токен",
    "Manual Upload": "Ручне завантаження",
    "March": "Березень",
    "Mark Accepted": "Позначити прийнятим",
    "Mark Rejected": "Позначити відхиленим",
    "Mark Submitted": "Позначити поданим",
    "Mark as primary activity code": "Позначити як основний код діяльності",
    "May": "Травень",
    "Message Delivery error": "Помилка доставки повідомлення",
    "Message from tax authority": "Повідомлення від податкової",
    "Messages": "Повідомлення",
    "Mode": "Режим",
    "Month": "Місяць",
    "My Activity Deadline": "Мій дедлайн активності",
    "Name": "Назва",
    "New": "Новий",
    "Next Activity Deadline": "Дедлайн наступної активності",
    "Next Activity Summary": "Опис наступної активності",
    "Next Activity Type": "Тип наступної активності",
    "No KEP configuration found for company %s.": "Налаштування КЕП для компанії %s не знайдено.",
    "No KEP configuration found for company %s. Please configure Tax Cabinet connection with KEP authentication.": "Налаштування КЕП для компанії %s не знайдено. Будь ласка, налаштуйте підключення до Податкового кабінету з автентифікацією КЕП.",
    "No XML content": "Немає вмісту XML",
    "No XML file to export": "Немає XML файлу для експорту",
    "No XML file to sign": "Немає XML файлу для підписання",
    "No XML file to submit": "Немає XML файлу для подання",
    "No authorization token.\\n\\nPlease paste the signed authorization token from browser Developer Tools.": "Немає токена авторизації.\\n\\nБудь ласка, вставте підписаний токен авторизації з інструментів розробника браузера.",
    "No new documents found.": "Нових документів не знайдено.",
    "No signed file. Please sign the document first.": "Немає підписаного файлу. Спочатку підпишіть документ.",
    "No valid authorization. Configure KEP key or provide auth token.": "Немає дійсної авторизації. Налаштуйте ключ КЕП або надайте токен авторизації.",
    "Notes": "Примітки",
    "Notification": "Сповіщення",
    "November": "Листопад",
    "Number of Actions": "Кількість дій",
    "Number of errors": "Кількість помилок",
    "Number of messages requiring action": "Кількість повідомлень, що потребують дії",
    "Number of messages with delivery error": "Кількість повідомлень з помилкою доставки",
    "October": "Жовтень",
    "Open wizard to fill document data": "Відкрити майстер для заповнення даних документа",
    "Other": "Інше",
    "Other Document": "Інший документ",
    "PDF": "PDF",
    "PDF File": "PDF файл",
    "PDF Filename": "Назва PDF файлу",
    "Password for the private key file": "Пароль для файлу приватного ключа",
    "Paste the signed authorization token from browser Developer Tools (Authorization header value after logging into cabinet.tax.gov.ua).": "Вставте підписаний токен авторизації з інструментів розробника браузера (значення заголовка Authorization після входу в cabinet.tax.gov.ua).",
    "Path to IIT EUSignCP library": "Шлях до бібліотеки IIT EUSignCP",
    "Path to certificates directory (CA certs, user certs)": "Шлях до каталогу сертифікатів (сертифікати ЦСК, сертифікати користувача)",
    "Path to private key file (.dat, .jks, .pfx)": "Шлях до файлу приватного ключа (.dat, .jks, .pfx)",
    "Period": "Період",
    "Phone": "Телефон",
    "Place CA certificates in the certificates directory": "Розмістіть сертифікати ЦСК у каталозі сертифікатів",
    "Place your user certificates (.cer files) in the same directory": "Розмістіть ваші сертифікати користувача (.cer файли) у тому ж каталозі",
    "Please add files to upload": "Будь ласка, додайте файли для завантаження",
    "Please select a document type first.": "Спочатку виберіть тип документа.",
    "Please select or create a Tax Cabinet configuration first.": "Спочатку виберіть або створіть налаштування Податкового кабінету.",
    "Primary": "Основний",
    "Process": "Обробити",
    "Q1": "К1",
    "Q2": "К2",
    "Q3": "К3",
    "Q4": "К4",
    "Receipt": "Квитанція",
    "Receipt Type 1 (Accepted)": "Квитанція тип 1 (Прийнято)",
    "Receipt Type 2 (Registered)": "Квитанція тип 2 (Зареєстровано)",
    "Rejected": "Відхилено",
    "Report": "Звіт",
    "Reported Documents": "Подані документи",
    "Request": "Запит",
    "Reset to Draft": "Повернути в чернетку",
    "Response": "Відповідь",
    "Responsible User": "Відповідальний користувач",
    "SMS Delivery error": "Помилка доставки SMS",
    "Sent Correspondence": "Надіслана кореспонденція",
    "September": "Вересень",
    "Sequence": "Послідовність",
    "Sign & Export": "Підписати та експортувати",
    "Sign Document": "Підписати документ",
    "Sign document with KEP and download for external submission": "Підписати документ КЕП та завантажити для зовнішнього подання",
    "Sign, encrypt and submit document to cabinet.tax.gov.ua": "Підписати, зашифрувати та подати документ до cabinet.tax.gov.ua",
    "Signed File": "Підписаний файл",
    "Signed Filename": "Назва підписаного файлу",
    "Signed authorization token (for manual auth)": "Підписаний токен авторизації (для ручної автентифікації)",
    "Signing failed: %s": "Помилка підписання: %s",
    "Single Tax Declaration (FOP)": "Декларація єдиного податку (ФОП)",
    "Single Tax Declaration (FOP) v8": "Декларація єдиного податку (ФОП) v8",
    "Single Tax Declaration (FOP) v9": "Декларація єдиного податку (ФОП) v9",
    "Source": "Джерело",
    "State": "Стан",
    "Status": "Статус",
    "Status Message": "Повідомлення статусу",
    "Status based on activities\\nOverdue: Due date is already passed\\nToday: Activity date is today\\nPlanned: Future activities.": "Статус на основі активностей\\nПрострочено: Термін вже минув\\nСьогодні: Дата активності сьогодні\\nЗаплановано: Майбутні активності.",
    "Submission failed: %s": "Помилка подання: %s",
    "Submission failed: %s %s": "Помилка подання: %s %s",
    "Submit to Cabinet": "Подати до кабінету",
    "Submitted": "Подано",
    "Submitted successfully: %s": "Успішно подано: %s",
    "Success": "Успіх",
    "Sync Complete": "Синхронізацію завершено",
    "Sync Date": "Дата синхронізації",
    "Sync Documents": "Синхронізувати документи",
    "Sync Settings": "Налаштування синхронізації",
    "Sync failed: %s": "Помилка синхронізації: %s",
    "Sync from Cabinet": "Синхронізувати з кабінету",
    "Sync from Cabinet API": "Синхронізувати з API кабінету",
    "Sync with Tax Cabinet": "Синхронізувати з Податковим кабінетом",
    "Tax Cabinet": "Податковий кабінет",
    "Tax Cabinet API": "API Податкового кабінету",
    "Tax Cabinet Configuration": "Налаштування Податкового кабінету",
    "Tax Cabinet Configurations": "Налаштування Податкового кабінету",
    "Tax Cabinet Document": "Документ Податкового кабінету",
    "Tax Cabinet Sync Wizard": "Майстер синхронізації Податкового кабінету",
    "Tax Cabinet Sync Wizard File": "Файл майстра синхронізації Податкового кабінету",
    "Tax Document": "Податковий документ",
    "Tax Document Data Wizard": "Майстер даних податкового документа",
    "Tax Document Type": "Тип податкового документа",
    "Tax Documents": "Податкові документи",
    "Tax Invoice": "Податкова накладна",
    "Tax Notification": "Податкове повідомлення",
    "Taxpayer Code": "Код платника податків",
    "Taxpayer Information": "Інформація про платника податків",
    "Taxpayer Name": "Назва платника податків",
    "Test Connection": "Перевірити підключення",
    "This Year": "Цей рік",
    "Type of the exception activity on record.": "Тип виключення активності в записі.",
    "Upload Documents": "Завантажити документи",
    "Upload Files": "Завантажити файли",
    "VAT Declaration": "Декларація з ПДВ",
    "Website Messages": "Повідомлення вебсайту",
    "Website communication history": "Історія комунікації вебсайту",
    "Wizard": "Майстер",
    "XML": "XML",
    "XML Content": "Вміст XML",
    "XML File": "XML файл",
    "XML Filename": "Назва XML файлу",
    "Year": "Рік",
    "e.g. Tax Cabinet Connection": "напр. Підключення до Податкового кабінету",
    "id": "id",
    "iit.com.ua": "iit.com.ua",
    "<em>Note: Password is never stored. You will be prompted for it when needed.</em>": "<em>Примітка: Пароль не зберігається. Вас попросять ввести його за потреби.</em>",
    "<strong>Authentication:</strong> Uses KEP (qualified electronic signature).": "<strong>Автентифікація:</strong> Використовує КЕП (кваліфікований електронний підпис).",
    "<strong>Security Notice:</strong> Your password is not stored and will only be used for this operation.": "<strong>Повідомлення безпеки:</strong> Ваш пароль не зберігається і буде використаний лише для цієї операції.",
    "Action": "Дія",
    "All Documents": "Всі документи",
    "Confirm": "Підтвердити",
    "Document signing requires password wizard - not yet implemented.": "Підписання документа потребує майстра паролів - ще не реалізовано.",
    "Document submission requires password wizard - not yet implemented.": "Подання документа потребує майстра паролів - ще не реалізовано.",
    "Enter KEP Password": "Введіть пароль КЕП",
    "Enter KEP password": "Введіть пароль КЕП",
    "Imported %d documents": "Імпортовано %d документів",
    "KEP Password Wizard": "Майстер пароля КЕП",
    "KEP key file is required. Please upload your private key.": "Потрібен файл ключа КЕП. Будь ласка, завантажте ваш приватний ключ.",
    "KEP key not configured.\\n\\nPlease upload your private key file in the Tax Cabinet connection settings.": "Ключ КЕП не налаштовано.\\n\\nБудь ласка, завантажте файл приватного ключа в налаштуваннях підключення до Податкового кабінету.",
    "KEP password is required for signing.": "Пароль КЕП необхідний для підписання.",
    "Key Filename": "Назва файлу ключа",
    "Make sure KEP key file is uploaded in the configuration. Password will be requested when syncing.": "Переконайтеся, що файл ключа КЕП завантажено в налаштуваннях. Пароль буде запитано під час синхронізації.",
    "No KEP configuration found for company %s. Please configure Tax Cabinet connection.": "Налаштування КЕП для компанії %s не знайдено. Будь ласка, налаштуйте підключення до Податкового кабінету.",
    "Password for your private key (not stored)": "Пароль для вашого приватного ключа (не зберігається)",
    "Sync Mode": "Режим синхронізації",
    "Sync Options": "Параметри синхронізації",
    "Upload your private key file (.dat, .jks, .pfx)": "Завантажте файл приватного ключа (.dat, .jks, .pfx)",
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
