# Доставка

← [Назад до головної](../README.md)

Легенда статусів: ✅ Стабільний · 🟢 Робочий · 🟡 Бета · 📦 Збірка

| Модуль | Версія | Статус | Призначення |
|--------|--------|--------|-------------|
| `l10n_ua_delivery_base` | 19.0.1.0.0 | 🟢 | Базовий модуль перевізників: налаштування, довідник відділень |
| `l10n_ua_delivery_novaposhta` | 19.0.1.0.0 | 🟡 | Нова Пошта (каркас) |
| `l10n_ua_delivery_ukrposhta` | 19.0.1.0.0 | 🟡 | Укрпошта (каркас) |
| `l10n_ua_delivery_meest` | 19.0.1.0.0 | 🟡 | Meest (каркас) |

> Стан домену: реалізовано лише інфраструктуру (базові поля перевізника та довідник
> відділень). Інтеграції API перевізників наразі — заготовки: усі методи створення ТТН,
> розрахунку вартості, відстеження та синхронізації довідників містять `# TODO` і
> повертають нульові значення. Автоматизованих тестів у домені немає.

---

## l10n_ua_delivery_base — Базовий модуль

**Залежності:** `delivery`, `l10n_ua_account_base`

Надає спільну інфраструктуру для українських перевізників.

### delivery.carrier (розширення) — реалізовано

Додає поля конфігурації до перевізника Odoo:

- `ua_carrier_type` — тип перевізника (`novaposhta` / `meest` / `ukrposhta`)
- `ua_api_key` — ключ API
- `ua_sender_ref`, `ua_sender_address_ref`, `ua_sender_contact_ref` — референси
  відправника в системі перевізника
- `ua_default_service_type` — тип послуги: склад-склад, склад-двері, двері-склад,
  двері-двері (за замовчуванням `warehouse`)
- `ua_default_payment_method` — платник: відправник / отримувач / третя сторона
- `ua_cod_enabled` — увімкнення післяплати (COD)

### l10n_ua.delivery.warehouse — реалізовано

Спільна модель відділень / поштоматів (довідник), працездатна:

- Поля: `name`, `carrier_type`, `warehouse_ref`, `warehouse_number`, `warehouse_type`
  (склад / поштомат / вантажний), `city`, `city_ref`, `address`, `phone`, `schedule`,
  `max_weight`, `latitude`, `longitude`, `active`
- Обмеження унікальності `UNIQUE(warehouse_ref, carrier_type)`
- Кастомний `name_search` — пошук за назвою, номером відділення та містом
- Форма, список, пошук, пункти меню

### l10n_ua.delivery.mixin — заготовка

Абстрактний mixin `l10n_ua.delivery.mixin` з інтерфейсом методів, які мають
перевизначати конкретні модулі перевізників. Усі методи наразі викидають
`NotImplementedError`:

- `ua_create_shipment(picking)` — створення відправлення / ТТН
- `ua_get_tracking(tracking_number)` — відстеження
- `ua_calculate_cost(order)` — розрахунок вартості
- `ua_get_warehouses(city)` — довідник відділень
- `ua_print_label(picking)` — друк маркування

---

## l10n_ua_delivery_novaposhta — Нова Пошта

**Залежності:** `l10n_ua_delivery_base`

Каркас інтеграції з API Нової Пошти. Додає до `delivery.carrier` поле `np_api_url`
(за замовчуванням `https://api.novaposhta.ua/v2.0/json/`).

| Метод | Стан |
|-------|------|
| `np_rate_shipment` — розрахунок вартості | 🟡 заглушка (`TODO`, повертає `price=0.0`) |
| `np_send_shipping` — створення ТТН | 🟡 заглушка (`TODO`, порожній `tracking_number`) |
| `np_get_tracking_link` — посилання відстеження | 🟢 формує URL із `carrier_tracking_ref` |
| `np_cancel_shipment` — скасування ТТН | 🟡 заглушка (`TODO`, `pass`) |
| `np_sync_warehouses` — синхронізація відділень | 🟡 заглушка (`TODO`, `pass`) |

Реальних викликів API, друку маркування та завантаження довідника відділень поки немає.

---

## l10n_ua_delivery_ukrposhta — Укрпошта

**Залежності:** `l10n_ua_delivery_base`

Каркас інтеграції з API Укрпошти. Полів у `delivery.carrier` не додає.

| Метод | Стан |
|-------|------|
| `ukrposhta_rate_shipment` — розрахунок вартості | 🟡 заглушка (`TODO`, `price=0.0`) |
| `ukrposhta_send_shipping` — створення накладної | 🟡 заглушка (`TODO`) |
| `ukrposhta_get_tracking_link` — посилання відстеження | 🟢 формує URL із `carrier_tracking_ref` |
| `ukrposhta_cancel_shipment` — скасування | 🟡 заглушка (`TODO`, `pass`) |
| `ukrposhta_sync_branches` — синхронізація відділень | 🟡 заглушка (`TODO`, `pass`) |

Реальної інтеграції API немає.

---

## l10n_ua_delivery_meest — Meest

**Залежності:** `l10n_ua_delivery_base`

Каркас інтеграції з API Meest. Полів у `delivery.carrier` не додає.

| Метод | Стан |
|-------|------|
| `meest_rate_shipment` — розрахунок вартості | 🟡 заглушка (`TODO`, `price=0.0`) |
| `meest_send_shipping` — створення накладної | 🟡 заглушка (`TODO`) |
| `meest_get_tracking_link` — посилання відстеження | 🟢 формує URL із `carrier_tracking_ref` |
| `meest_cancel_shipment` — скасування | 🟡 заглушка (`TODO`, `pass`) |
| `meest_sync_warehouses` — синхронізація відділень | 🟡 заглушка (`TODO`, `pass`) |

Реальної інтеграції API немає.
