# Ukraine - Budget Treasury DBF Import

[![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0-standalone.html)

Плагін до `l10n_ua_budget_treasury`, що додає підтримку реальних
виписок ДКСУ у форматі DBase III/IV.

## Що дає модуль

* **Pure-Python парсер DBF** (без `dbfread` чи інших залежностей)
* Override `_parse_custom()` у `l10n_ua.treasury.statement.import` —
  обробляє `file_format = 'custom'` як DBF
* Маппінг типових полів Казначейства (DOC_NUM, DOC_DATE, SUM_,
  NAZ_PRIZ, KOD_KOR, NAZ_KOR, DT_KT)
* Hook `_dbf_field_map()` для переозначення в дочірньому модулі
  під конкретний формат клієнта

## Підтримувані поля

| Канонічне ім'я | Можливі назви в DBF |
|---|---|
| doc_num | DOC_NUM, NUM_DOC, N_DOC, DOCNO, NUMDOC |
| doc_date | DOC_DATE, DATA_DOC, DATEV, DATE_DOC, DAT, DATA |
| amount | SUM_, SUMA, SUM, AMOUNT, SUM_DOC |
| purpose | NAZ_PRIZ, PRIZN, PRIZNACH, PURPOSE, PRYZNACH, NAZN |
| partner_edrpou | KOD_KOR, EDRPOU, KOD_OS, KOD_PART, OKPO_KOR |
| partner_name | NAZ_KOR, NAZ_OS, PARTN, NAZW_KOR, KOR_NAME |
| direction | DT_KT, KOD_OPER, DBKR, TYPE_OP |

## Кодування

За замовчуванням — **CP866** (стандарт DBase III, Russian DOS). Українські
літери «і», «ї», «є» в cp866 відсутні — для них використовуйте **cp1251**
(Windows Cyrillic) або **UTF-8**. Кодування налаштовується в полі
«Encoding» wizard'а.

## Адаптація під специфічний формат

Якщо ваш конкретний експорт Казначейства використовує інші назви полів,
створіть дочірній модуль і переозначте `_dbf_field_map`:

```python
class L10nUaTreasuryStatementImport(models.TransientModel):
    _inherit = 'l10n_ua.treasury.statement.import'

    def _dbf_field_map(self):
        m = super()._dbf_field_map()
        m['amount'] = ['MY_FIELD', 'SUM_DOC'] + m['amount']
        return m
```

## Обмеження

* Підтримуються лише типи полів C / N / D / L / F. Memo (M, BLOB) — пропускаються.
* Без real-world sample-файлу маппінг — best-effort. Якщо реальний формат
  суттєво відрізняється — переозначте через `_dbf_field_map()`.

## Тести

```bash
./venv/bin/odoo -d <db> -i l10n_ua_budget_treasury_dbf \
    --test-tags l10n_ua_budget_treasury_dbf --stop-after-init
```
