# Маркетплейси

← [Назад до головної](../README.md)

Легенда статусів: ✅ Стабільний · 🟢 Робочий · 🟡 Бета · 📦 Збірка

Домен об'єднує інтеграції з українськими маркетплейсами (Rozetka, Prom.ua) та
прайс-агрегаторами (Hotline, Price.ua). Ядром є `l10n_ua_marketplace_base`, яке
надає конфігурацію бекендів, імпорт замовлень, генерацію YML/XML-фідів, вебхуки та
крони. Конкретні маркетплейси підключаються окремими модулями, що успадковують
модель `marketplace.backend` і перевизначають методи `_api_*`.

| Модуль | Версія | Статус | Призначення |
|--------|--------|--------|-------------|
| `l10n_ua_marketplace_base` | 19.0.1.0.0 | 📦 | Ядро: бекенди, замовлення, прайслисти, фіди, вебхуки, крони |
| `l10n_ua_marketplace_rozetka` | 19.0.1.0.0 | 🟢 | Rozetka Seller API (замовлення, склад, ціни) |
| `l10n_ua_marketplace_prom` | 19.0.1.0.0 | 🟢 | Prom.ua API (замовлення, товари, склад, ціни) |
| `l10n_ua_marketplace_priceua` | 19.0.1.0.0 | 🟡 | Price.ua (лише YML-фід) |
| `l10n_ua_marketplace_hotline` | 19.0.1.0.0 | 🟡 | Hotline.ua (лише YML-фід) |

> Автоматизованих тестів (`tests/`) у жодному з модулів домену немає, тому статус
> ✅ не присвоюється.

---

## l10n_ua_marketplace_base — Ядро інтеграцій 📦

Базовий модуль-застосунок. Залежить від `sale`, `stock`, `delivery`, `account`.

**Моделі:**

- `marketplace.backend` — конфігурація підключення до маркетплейсу. Селекція типів
  (`rozetka`, `prom`, `epicentr`, `allo`, `hotline`, `priceua`), стан
  `draft → active → inactive`, налаштування фіду (`feed_enabled`, `feed_format`:
  YML/XML) і вебхуків (`webhook_enabled`). Успадковує `mail.thread`.
- `marketplace.order` / `marketplace.order.line` — замовлення з маркетплейсу.
  Стан `new → confirmed → shipped → delivered → cancelled`. Пошук/створення
  партнера за нормалізованим телефоном, генерація `sale.order`, реєстрація оплати,
  зв'язок з `stock.picking` та рахунками.
- `marketplace.pricelist` / `marketplace.pricelist.item` — набори товарів для
  вивантаження. Генерація позицій, обчислення SKU/ціни/залишку, публікація.
- `marketplace.category` — ієрархічний маппінг категорій маркетплейсу (`get_or_create`).
- `marketplace.status.mapping`, `marketplace.payment.status` — маппінг зовнішніх
  статусів замовлень/оплат на внутрішні стани Odoo.
- Розширення `product.template`, `product.product`, `res.partner` (лічильники та
  дії переходу до товарів/замовлень маркетплейсу).

**Генерація фідів** (`marketplace_pricelist.py`): реальний YML-каталог
(`yml_catalog` → `shop` → `offers`) через `lxml.etree`; XML наразі делегує до
YML-реалізації.

**Контролери** (`controllers/main.py`):

| Маршрут | Тип | Призначення |
|---------|-----|-------------|
| `/marketplace/feed/<backend_id>` | http, public | Віддача фіду (формат за замовч. бекенду) |
| `/marketplace/feed/<backend_id>/yml` | http, public | YML-фід |
| `/marketplace/feed/<backend_id>/xml` | http, public | XML-фід |
| `/marketplace/webhook/<backend_id>` | jsonrpc, public | Прийом вебхуків (нове замовлення / оновлення) з перевіркою підпису |
| `/marketplace/status` | http, public | Статус сервісу |

**Крони** (`data/ir_cron_data.xml`):

| Крон | Інтервал | Метод |
|------|----------|-------|
| Імпорт замовлень | 15 хв | `_cron_import_orders_all` |
| Синхронізація складу | 30 хв | `_cron_sync_stock_all` |
| Синхронізація цін | 1 год | `_cron_sync_prices_all` |
| Оновлення токенів | 12 год | `_cron_refresh_tokens` |

**API-контракт для дочірніх модулів** — методи `_api_authenticate`,
`_api_get_orders`, `_api_update_order_status`, `_api_cancel_order`,
`_api_sync_stock`/`_api_sync_prices` (та їх `_batch`-варіанти) у базі є заглушками
(`NotImplementedError`) і перевизначаються в модулях конкретних маркетплейсів.
Batch-методи мають дефолтну реалізацію через одиничні виклики.

---

## l10n_ua_marketplace_rozetka — Rozetka Seller API 🟢

Повноцінна інтеграція з `https://api-seller.rozetka.com.ua`. Залежить від
`l10n_ua_marketplace_base`, потребує `requests`. Успадковує `marketplace.backend`
та `marketplace.order`.

**Реалізовано:**

- `_api_authenticate` — Bearer-токен з автооновленням (`action_refresh_token`,
  `action_test_connection`).
- `_api_get_orders` — імпорт замовлень з пагінацією.
- `_api_update_order_status` — синхронізація статусів у Rozetka.
- `_sync_stock` / `_sync_prices` та `_api_sync_stock_batch` / `_api_sync_prices_batch`
  — пакетне оновлення залишків і цін.
- `action_sync_statuses` — маппінг статусів.
- `_api_cancel_order` — скасування замовлення (з розширенням
  `marketplace.order.cancel.wizard`).

Документація API: https://api-seller.rozetka.com.ua/apidoc/

---

## l10n_ua_marketplace_prom — Prom.ua API 🟢

Повноцінна інтеграція з `https://my.prom.ua/api/v1`. Залежить від
`l10n_ua_marketplace_base`, потребує `requests`. Успадковує `marketplace.backend`
та `marketplace.order`.

**Реалізовано:**

- `_api_authenticate` — Bearer-токен (без оновлення, `action_test_connection`).
- `_api_get_orders` — імпорт замовлень.
- `_api_update_order_status` — синхронізація статусів.
- `_sync_stock` / `_sync_prices` з пакетними варіантами.
- `action_import_products` — імпорт наявного каталогу Prom.ua у позиції прайслиста.
- `action_sync_statuses`, `_api_cancel_order` (з розширенням майстра скасування).

Документація API: https://public-api.docs.prom.ua/

---

## l10n_ua_marketplace_priceua — Price.ua 🟡

Тонке розширення для прайс-агрегатора Price.ua (лише фід, без API замовлень/складу).
Модель-розширення `marketplace.backend` (~50 рядків): додає поля
`priceua_merchant_id`, `priceua_feed_category_id` та дію `action_copy_feed_url`.
Тип `priceua` вже визначений у базі; сам YML-фід генерується ядром. Власної
бізнес-логіки за межами конфігурації фіду немає.

---

## l10n_ua_marketplace_hotline — Hotline.ua 🟡

Тонке розширення для прайс-агрегатора Hotline.ua (лише фід, без API). Аналогічне до
Price.ua: додає поля `hotline_merchant_id`, `hotline_feed_category_id` та дію
`action_copy_feed_url`. Тип `hotline` визначений у базі, фід формує ядро.
