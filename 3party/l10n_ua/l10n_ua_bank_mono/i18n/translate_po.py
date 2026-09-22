#!/usr/bin/env python3
"""Translate PO file for l10n_ua_hr_base module."""

import re

TRANSLATIONS = {
    # Common
    "Active": "Активний",
    "API Token": "API токен",
    "API returned error: %s": "API повернув помилку: %s",
    "Account ID": "ID рахунку",
    "Available Accounts": "Доступні рахунки",
    "Bank Sync Configuration": "Налаштування синхронізації банку",
    "Connected to monobank. Client: %s, Accounts: %d": "Підключено до monobank. Клієнт: %s, Рахунків: %d",
    "Connection failed: %s": "Помилка підключення: %s",
    "Could not determine monobank account ID": "Не вдалося визначити ID рахунку monobank",
    "Display Name": "Назва для відображення",
    "Failed to fetch accounts: %s": "Не вдалося отримати рахунки: %s",
    "Fetch Accounts": "Отримати рахунки",
    "ID": "ID",
    "No accounts found": "Рахунків не знайдено",
    "Please configure API Token": "Будь ласка, налаштуйте API токен",
    "Please configure monobank API Token": "Будь ласка, налаштуйте API токен monobank",
    "Provider": "Провайдер",
    "Rate limit exceeded. Please wait 60 seconds.": "Перевищено ліміт запитів. Будь ласка, зачекайте 60 секунд.",
    "Source": "Джерело",
    "Success": "Успіх",
    "Test Connection": "Перевірити підключення",
    "Ukrainian Bank Statement": "Українська банківська виписка",
    "Webhook Active": "Webhook активний",
    "Webhook URL": "URL Webhook",
    "monobank": "monobank",
    "monobank API": "API monobank",
    "monobank API allows maximum 31 days per request": "API monobank дозволяє максимум 31 день на запит",
    "monobank API error: %s": "Помилка API monobank: %s",
    "monobank API rate limit exceeded. Please wait 60 seconds.": "Перевищено ліміт запитів API monobank. Будь ласка, зачекайте 60 секунд.",
    "monobank Webhook": "Webhook monobank",
    "monobank account ID (optional, fetched automatically)": "ID рахунку monobank (необов'язково, отримується автоматично)",
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
