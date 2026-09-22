# Ціни постачальників

← [Назад до головної](../README.md)

Імпорт прайс-листів постачальників із різних джерел та форматів у `product.supplierinfo`. Базовий рушій + підключувані парсери форматів (CSV, XML, XLSX) та завантажувачі джерел (HTTP API, SFTP). Кожен модуль встановлюється незалежно — беріть лише потрібні формати й джерела.

> Детальний розбір архітектури, потоку даних і моделей: [supplier_prices_architecture.md](supplier_prices_architecture.md).

Легенда статусів: ✅ Стабільний · 🟢 Робочий · 🟡 Бета · 📦 Збірка

| Модуль | Версія | Статус | Призначення |
|--------|--------|--------|-------------|
| `l10n_ua_supplier_prices_base` | 19.0.1.0.0 | ✅ | Рушій: джерела, маппінг, state machine, JSON-парсер, ручне завантаження |
| `l10n_ua_supplier_prices_csv` | 19.0.1.0.0 | ✅ | Парсер CSV |
| `l10n_ua_supplier_prices_xml` | 19.0.1.0.0 | ✅ | Парсер XML (XPath) |
| `l10n_ua_supplier_prices_xlsx` | 19.0.1.0.0 | ✅ | Парсер XLSX (Excel) |
| `l10n_ua_supplier_prices_api` | 19.0.1.0.0 | ✅ | Завантажувач через HTTP API |
| `l10n_ua_supplier_prices_sftp` | 19.0.1.0.0 | ✅ | Завантажувач через SFTP |

Статуси: усі шість модулів мають реалізований код і робочі юніт-тести (base — 44 тести; csv — 10; xlsx — 13; xml — 9; api — 12; sftp — 10), тому позначені ✅.

---

## Загальна архітектура

Рушій розділяє процес на два незалежні розширювані шари, налаштовані на джерелі (`l10n_ua.supplier.price.source`):

- **fetcher_type** — звідки взяти файл: `manual` (базово), `api`, `sftp`.
- **parser_type** — як розібрати файл: `json` (базово), `csv`, `xml`, `xlsx`.

Кожен імпорт (`l10n_ua.supplier.price.import`) проходить state machine:

```
draft → fetching → fetched → parsing → parsed → applying → done
                                                            ↘ error
```

- `action_fetch` викликає `_do_fetch()` — заповнює `raw_file` / `raw_filename` (модулі-завантажувачі перевизначають через `super()`).
- `action_parse` викликає `_do_parse()` — розбирає `raw_file` у рядки `l10n_ua.supplier.price.import.line` за маппінгом (модулі-парсери перевизначають через `super()`).
- `action_apply` викликає `_do_apply()` — створює/оновлює `product.supplierinfo` для кожного рядка.

Raw-файл зберігається, тож парсинг можна повторити без повторного завантаження (`action_restart`). Watchdog-крон повертає «застряглі» імпорти в `error`, а крон авто-синхронізації створює нові імпорти за інтервалом джерела.

Детальніше — у [supplier_prices_architecture.md](supplier_prices_architecture.md).

---

## `l10n_ua_supplier_prices_base` — рушій ✅

Залежності: `product`, `purchase`, `mail`, `l10n_ua_account_base`.

Ключові моделі:

- **`l10n_ua.supplier.price.source`** — джерело: постачальник (`partner_id`), компанія, `fetcher_type` / `parser_type`, маппінг, валюта за замовчуванням, дія на невідомий SKU (`unknown_sku_action`: `skip` / `log_only` / `create_product` / `error_stop`), авто-синхронізація (`auto_sync_active`, `sync_interval_hours`), таймаути (`fetch_timeout`, `parse_timeout`, `apply_timeout`, `watchdog_timeout_minutes`), `connection_config` (JSON для завантажувачів). Успадковує `mail.thread`.
- **`l10n_ua.supplier.price.mapping`** + **`.mapping.field`** — маппінг: `record_path` (шлях до записів), `parser_config` (JSON з параметрами конкретного парсера) та рядки полів. Поле маппінгу описує `target` (sku, name, price, currency, qty_min, uom, date_valid, barcode, description), `source_path`, `required`, `default_value`, `transform` + `transform_param`.
- **`l10n_ua.supplier.price.import`** — прогін імпорту зі state machine, лічильниками (`line_count`, `matched_count`, `unknown_count`, `error_count`) та `error_log`. Містить вбудований JSON-парсер (`_parse_json`).
- **`l10n_ua.supplier.price.import.line`** — рядок прайсу. `_find_product()` шукає товар за `product.supplierinfo` (partner + `product_code`); `_apply_to_supplierinfo()` створює/оновлює запис постачальника; `_handle_unknown_sku()` обробляє невідомі SKU згідно з політикою джерела.

Інструменти (`tools/`):

- `transforms.apply_transform` — перетворення значень: `strip`, `upper`, `lower`, `replace_comma`, `to_float`, `to_decimal`, `parse_date`, `multiply`.
- `json_path` — вибірка значень за шляхом (`items[*].price.value`) для JSON-парсера.

Дані: послідовності (`ir_sequence_data.xml`) та крони watchdog/авто-синхронізації (`ir_cron_data.xml`). Є views, меню й права доступу.

Тести (44): JSON-парсер, json_path, transforms, state machine.

---

## `l10n_ua_supplier_prices_csv` — парсер CSV ✅

Додає `parser_type = 'csv'`; перевизначає `_do_parse()` → `_parse_csv()`.

`parser_config` (JSON на маппінгу): `delimiter` (`,`), `encoding` (`utf-8` з fallback на `utf-8-sig`, `windows-1251`, `cp1251`), `has_header`, `skip_rows`, `quotechar`. За `has_header=True` `source_path` — назва колонки; за `False` — індекс колонки (0-based). Розрахований на українські прайси: кодування cp1251, `;` як роздільник, кома як десятковий (через transform `replace_comma`/`to_float`).

Тести (10): заголовок/індекс, `;`-роздільник, windows-1251 та fallback-кодування, десяткова кома, `skip_rows`, помилки required, дефолти й невалідний JSON-конфіг.

---

## `l10n_ua_supplier_prices_xml` — парсер XML ✅

Залежність Python: `lxml`. Додає `parser_type = 'xml'`; перевизначає `_do_parse()` → `_parse_xml()`.

`record_path` на маппінгу — XPath до елементів-записів (`//product`). `source_path` на полях — відносний XPath: `./code/text()`, `@sku`, `./price/@value`, `string(./name)`. `parser_config`: `namespaces` (мапа префіксів NS) та `encoding` (примусова заміна; 1С часто віддає cp1251 у declaration).

Тести (9): текстові шляхи, атрибути, вкладені атрибути, namespaces, примусове windows-1251, відсутність збігів за record_path, невалідний XML/XPath, відсутнє required-поле.

---

## `l10n_ua_supplier_prices_xlsx` — парсер XLSX ✅

Залежність Python: `openpyxl`. Додає `parser_type = 'xlsx'`; перевизначає `_do_parse()` → `_parse_xlsx()`.

`parser_config`: `sheet_name` (ім'я/індекс, default — перший лист), `header_row` (1-based), `has_header`, `skip_rows`. `source_path`: за `has_header=True` — назва колонки; за `False` — літера (`A`, `AC`) або індекс (`0`, `1`). Дати (datetime) повертаються як date; числові ціни вже float.

Тести (13): літера→індекс колонки, заголовок/літера/індекс, конкретний лист, `skip_rows`, `header_row=2`, пропуск порожніх рядків, числова ціна без transform, відсутній лист, невалідний файл, відсутнє required-поле.

---

## `l10n_ua_supplier_prices_api` — завантажувач HTTP API ✅

Залежність Python: `requests`. Додає `fetcher_type = 'api'`; перевизначає `_do_fetch()` → `_fetch_api()`.

`connection_config` (JSON на джерелі): `url`, `method` (GET/POST), `auth_type` (`none` / `basic` / `bearer` / `api_key_header`), облікові дані (`username`/`password`/`token`/`header_name`), додаткові `headers`, `params`, `body`, а також `response_type`:

- `file` (default) — тіло відповіді і є файлом → `raw_file`.
- `json_indirect` — відповідь JSON з посиланням; URL береться за `json_indirect_path` і робиться другий запит.

Timeout — з `source.fetch_timeout`.

Тести (12, з мокнутим `requests.Session`): простий GET, ім'я файлу з URL, basic/bearer/api_key auth, `json_indirect`, timeout, HTTP-помилка, відсутній URL, невалідний конфіг, невідомий auth_type, повний пайплайн fetch→parse.

---

## `l10n_ua_supplier_prices_sftp` — завантажувач SFTP ✅

Залежність Python: `paramiko`. Додає `fetcher_type = 'sftp'`; перевизначає `_do_fetch()` → `_fetch_sftp()`.

`connection_config` (JSON на джерелі): `host`, `port` (22), `username`, автентифікація через `password` або `key_file` (+`key_passphrase`), `remote_path`, `host_key_policy` (`reject` default / `auto_add` / `warning`).

⚠️ Наразі облікові дані зберігаються у `connection_config` відкритим текстом; для production варто винести в `ir.config_parameter` чи зашифроване сховище.

Тести (10, з мокнутим `paramiko.SSHClient`): автентифікація паролем/ключем, нестандартний порт, помилки автентифікації/з'єднання, відсутній віддалений файл, відсутнє обов'язкове поле конфігу, відсутній метод авторизації, невідома host_key_policy, повний пайплайн sftp→parse.

---

## Встановлення

```bash
# Мінімальний набір: рушій + CSV-парсер
./venv311/bin/odoo -d odoo19ndev -i l10n_ua_supplier_prices_base,l10n_ua_supplier_prices_csv --stop-after-init

# Повний набір (усі парсери й завантажувачі)
./venv311/bin/odoo -d odoo19ndev -i l10n_ua_supplier_prices_base,l10n_ua_supplier_prices_csv,l10n_ua_supplier_prices_xml,l10n_ua_supplier_prices_xlsx,l10n_ua_supplier_prices_api,l10n_ua_supplier_prices_sftp --stop-after-init
```

Зовнішні Python-залежності за модулями: `xml` → `lxml`, `xlsx` → `openpyxl`, `api` → `requests`, `sftp` → `paramiko`.
