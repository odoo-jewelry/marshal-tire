# Оценка реализации

## Итог

- Всего сценариев: 17
- Implementation-driving сценариев: 6
- Verification-only сценариев: 11
- Implementation clusters: 4
- Implementation units: 6
- Fast path: нет
- Эмпирический размер: medium
- Производительность: 1 час на implementation unit
- Базовая оценка: 6 часов
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 5–8 часов
- Уверенность: средне-высокая при предварительно реализованном `revise-purchase-price-control-actions`

Итоговая оценка — реалистичное активное рабочее время мидл Odoo-разработчика от начала реализации данного delta до готового и обычно проверенного изменения. Focused tests, static checks, один module update и обычный non-browser smoke включены в clusters.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| purchase-price-control | Exclude recoverable purchase tax from standard cost | implementation-driving | C1 | stock, accounting | Требует нового valuation-compatible значения на строке через standard helper |
| purchase-price-control | Include a tax that belongs in inventory value | verification-only | C1 | accounting | Проверяет tax semantics того же стандартного helper |
| purchase-price-control | Convert purchase unit and currency for standard cost | verification-only | C1 | stock | Проверяет UoM/currency/date ветви переиспользованного helper |
| purchase-price-control | Fill a standard-cost snapshot | implementation-driving | C2 | migration | Нужны stored snapshot field и расширение Fill/refresh |
| purchase-price-control | Keep the standard-cost snapshot stable | verification-only | C2 | migration | Проверяет stored semantics общего snapshot mechanism |
| purchase-price-control | Offer Update for only a standard-cost discrepancy | implementation-driving | C2 | view-conflict | Требует третьей comparison pair и UI visibility |
| purchase-price-control | Update a Standard Price product from one line | implementation-driving | C3 | stock, accounting, security | Нужна условная обычная ORM-запись `standard_price` и refresh |
| purchase-price-control | Retry after a successful standard-cost update | verification-only | C2, C3 | accounting | Проверяет no-op после общего refresh без новой history |
| purchase-price-control | Update standard costs in bulk | implementation-driving | C4 | stock, accounting, bulk | Расширяет frozen bulk payload и product writes |
| purchase-price-control | Resolve repeated Standard Price products deterministically | implementation-driving | C4 | accounting, bulk | Требует final-per-product cost target без промежуточной history |
| purchase-price-control | Roll back a failed standard-cost bulk update | verification-only | C4 | accounting, bulk, security | Проверяет стандартную транзакционность всего payload |
| purchase-price-control | Preserve AVCO cost behavior | verification-only | C3, C4 | stock | Проверяет gating текущим cost method |
| purchase-price-control | Preserve FIFO cost behavior | verification-only | C3, C4 | stock | Проверяет тот же gating и отсутствие lot cost writes |
| purchase-price-control | Preserve standard cost consequences | verification-only | C3 | stock, accounting | Проверяет штатные `product.value` и lot propagation стандартной ORM-записи |
| purchase-price-control | Keep standard cost company-specific | verification-only | C2, C3 | security | Проверяет `with_company(order.company_id)` общего механизма |
| purchase-price-control | Reject an unauthorized standard-cost update | verification-only | C3, C4 | accounting, security | Проверяет права и rollback без custom `sudo()` |
| purchase-price-control | Confirm without a standard-cost side effect | verification-only | C3 | procurement, accounting | Проверяет отсутствие новых lifecycle hooks |

Классификация:

- `implementation-driving` — требует нового или изменённого production-поведения;
- `verification-only` — покрывается тем же механизмом либо проверяет стандартный Odoo handoff, права, транзакционность или отсутствие регрессии.

Каждый из 17 Scenario присутствует в таблице ровно один раз.

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | `valuation_purchase_price` через стандартный valuation helper и явная dependency `purchase_stock` | Tax treatment, discount/UoM/currency/date valuation cost | 1 | Один известный extension point без дублирования формулы Odoo |
| C2 | Stored `current_standard_price`, Fill/refresh, cost-method exposure, discrepancy и узкое view extension | Snapshot, stability, cost-only action visibility, retry/company context | 1 | Небольшое расширение уже установленного snapshot/discrepancy паттерна базового change |
| C3 | Условная line-level запись `standard_price` через обычный product ORM | Standard write, history/lot effects, AVCO/FIFO isolation, права, lifecycle regression | 2 | Стандартный handoff между Purchase Price Control и Stock Accounting с focused validation |
| C4 | Bulk final-standard-cost payload, last-line-wins и общий atomic refresh | Bulk update, repeated product, rollback, AVCO/FIFO gating | 2 | Согласованное изменение нескольких строк/продуктов, но на существующем ordered payload базового change |

Сумма: `1 + 1 + 2 + 2 = 6` implementation units.

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет. Tax, UoM/currency, line, bulk, method isolation, permissions и lifecycle уже разделены.

### Дублирующиеся или пересекающиеся сценарии

- AVCO и FIFO используют один production gating, но оставлены отдельными из-за разных valuation algorithms и регрессионного риска.
- Bulk rollback и unauthorized update пересекаются по atomicity, но второй отдельно фиксирует access-control outcome.

### Недостающие сценарии

- Нет: Standard/AVCO/FIFO, налоги, UoM/валюта, Fill, line/bulk, конфликты, history/lots, права, multi-company, retry и lifecycle покрыты.

### Недостаточно определённые или противоречивые сценарии

- Delta предполагает целевое состояние незавершённого `revise-purchase-price-control-actions`; без него public actions и snapshot fields отсутствуют. Эта зависимость явно отражена в design и tasks.
- «Закупочная цена» разделена на tax-included reference price и valuation-compatible cost; в `standard_price` записывается только второе значение.

## Расчёт трудозатрат

- Сумма implementation units: 6
- Hours per unit: 1
- Базовые часы: 6
- Discovery: 0 — стандартные Purchase Stock и Stock Accounting extension points исследованы
- Миграция или обработка данных: 0 — стандартное создание column, без backfill
- Production-like bulk/external coordination/special hardware: 0
- Необычная длительная или ручная проверка: 0
- Другие исключительные конкретные работы: 0
- Итоговый диапазон: 5–8 часов

Разброс отражает focused accounting/lot verification и repeated-product bulk history. Обычные тесты, module update и smoke повторно не добавляются.

## Стратегия проверки

### Автоматизированные тесты

- Требуются.
- Обоснование: меняются `standard_price`, accounting history, lot propagation, bulk ordering, права и company-dependent данные.
- Минимальный набор: valuation cost taxes/UoM/currency/date; Fill/refill/stability; cost-only discrepancy; Standard line Update и retry; Update All с repeated product; normal history и lots; AVCO/FIFO isolation; method switch; company isolation; AccessError/rollback; lifecycle без side effects.

### Module update и smoke verification

- Python syntax/imports, manifest dependency и version.
- XML parse, view inheritance, fields и translations.
- Обновление `purchase_price_control` на явной development DB с focused backend suite.
- Проверка нового stored column без backfill и сохранения uninitialized state существующих строк.
- Ручной non-browser smoke standard-cost колонок и action visibility в draft, confirmed, locked и cancelled PO. Browser automation не запускается.

## Основные факторы сложности

- Разделение commercial tax-included reference price и inventory valuation cost.
- Стандартные accounting/lot consequences обычной записи `standard_price`.
- Final-only cost history при нескольких bulk lines одного продукта.
- Company-dependent cost и смена effective cost method между Fill и Update.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| stock | Неверная цена способна изменить оценку Standard Price и lot costs | Standard valuation helper, Standard/AVCO/FIFO и lot tests |
| accounting | Product write создаёт `product.value` и влияет на cost history | Не обходить ORM; проверять одну итоговую history entry и rollback |
| bulk | Повторяющиеся продукты могут создать промежуточную history | Frozen payload и final cost target на `(company, product)` |
| security | Cost write не должен обходить product/company access | `with_company`, без custom `sudo()`, representative user tests |
| migration | Новый stored snapshot column на существующих строках | Общий initialization flag, без backfill, module update test |
| procurement | PO lifecycle не должен получить скрытый cost side effect | Confirm/approve/cancel/reset/lock/receipt regressions |
| view-conflict | Дополнительные поля зависят от cost method в embedded list | Узкий XPath, XML compilation и ручной smoke |
| uncertainty | Базовый action-driven change ещё не реализован | Строгая последовательность apply либо объединение artifacts до реализации |

## Предположения

- `revise-purchase-price-control-actions` реализован и проверен до начала этого delta либо оба changes реализуются согласованно одним рабочим циклом.
- `_get_stock_move_price_unit()` остаётся стандартным источником valuation-compatible стоимости PO line в установленном Odoo 19.
- `standard_price` пишется только по текущему effective `cost_method == "standard"` в order company.
- Cost-only discrepancy делает существующий Update доступным; отдельной cost-кнопки нет.
- Для повторяющегося продукта bulk записывает только final standard cost последней candidate line.
- Стандартный внутренний `sudo()` Stock Accounting после разрешённой product write сохраняется без custom обходов.

## Исключено из оценки

- Реализация самого `revise-purchase-price-control-actions`.
- Изменение AVCO/FIFO, stock moves, bills, landed costs, closing и исторической оценки.
- Backfill существующих PO snapshots, cleanup DB и отдельная history model.
- Новая security group, wizard, browser automation, production deployment.

## Требуется discovery

- Нет.
- Обоснование: custom addon, базовый planned change, standard valuation helper и product cost write Odoo 19 уже исследованы. Остаточные риски покрываются focused tests.

## Условия пересмотра оценки

- Доработку потребуется реализовывать до или вместо базового action-driven change без объединения планов.
- В `standard_price` потребуется записывать tax-included reference price вопреки valuation helper.
- Нужно разрешить custom cost update для AVCO/FIFO или частичный success bulk.
- Потребуется отдельное подтверждение, security group, audit model или исторический backfill.
- Standard cost должен обновляться на receipt/bill/confirm, а не только explicit Update.
- Repeated products должны создавать историю каждой промежуточной строки, а не только final target.

## Фактический результат

Заполняется после реализации:

- Фактические часы:
- Отклонение от оценки:
- Причина отклонения:
- Фактические часы на unit:
- Изменения для будущей калибровки:
