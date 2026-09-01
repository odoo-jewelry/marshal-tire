## Context

Этот change расширяет целевую архитектуру `revise-purchase-price-control-actions`: `purchase.order.line` хранит снимки текущих цен, рассчитывает `effective_purchase_price` и `planned_sale_price`, а явные `Update`/`Update All` записывают `last_purchase_price` и `lst_price`. Базовый change ещё не реализован, поэтому данная доработка должна применяться после него либо быть объединена с ним перед реализацией.

`last_purchase_price` имеет намеренную справочную семантику: tax-included цена после скидки в валюте компании за базовую UoM. Она не подходит для `standard_price`, потому что Odoo исключает возмещаемые налоги из складской стоимости и включает только налоги без отдельного account assignment. В установленном Odoo 19 это уже реализовано в `purchase.order.line._get_stock_move_price_unit()`: helper применяет скидку, `total_void`, UoM, валюту, дату курса и точность Product Price. `purchase_stock.stock.move._get_value_from_quotation()` использует тот же helper как источник складской стоимости из PO.

`product.product.standard_price` является company-dependent. Обычная запись этого поля для Standard Price проходит через `stock_account`: создаёт стандартную запись `product.value` с датой и пользователем и распространяет стоимость на lot-valuated партии по штатным правилам. Для AVCO/FIFO `_update_standard_price()` вызывается складской оценкой; custom price-control не должен конкурировать с этим механизмом.

## Goals / Non-Goals

**Goals:**

- синхронизировать `standard_price` из явных действий Price Control только при текущем `cost_method == "standard"`;
- использовать оценочную закупочную стоимость Odoo, отличную от tax-included `effective_purchase_price`;
- сделать расхождение standard cost самостоятельной причиной доступности `Update`/`Update All`;
- сохранить снимки, deterministic bulk ordering, атомарность, права и company isolation базового change;
- сохранить стандартные `product.value` и lot-cost последствия обычной записи `standard_price`;
- гарантировать отсутствие custom-записи `standard_price` для AVCO/FIFO и без явного action.

**Non-Goals:**

- изменение стандартных AVCO/FIFO алгоритмов, stock moves, bills, returns, landed costs или closing;
- использование tax-included `effective_purchase_price` как учётной себестоимости;
- автоматическое изменение стоимости при confirm/approve/receipt/cancel/reset/lock/unlock;
- пересчёт исторической складской оценки или backfill исторических PO lines;
- отдельная модель истории вместо стандартного `product.value`;
- отдельное управление стоимостью конкретных партий;
- настройка `cost_method` из Purchase Order.

## Decisions

### 1. Затрагиваемые компоненты и зависимость

Изменяется только addon `main/purchase_price_control` после реализации базового action-driven change:

- `__manifest__.py`: добавить явную зависимость `purchase_stock` и поднять версию;
- `models/purchase_order_line.py`: standard-cost snapshot, рассчитанная оценочная стоимость, discrepancy и line-action payload;
- `models/purchase_order.py`: Fill, Update All, final payload selection и refresh связанных строк;
- `views/purchase_order_views.xml`: показать текущую и рассчитанную standard cost только для строк Standard Price;
- `tests/test_purchase_price_control.py`: сфокусированные stock/accounting, permission, multi-company и rollback tests;
- `i18n/purchase_price_control.pot`, `i18n/ru.po`, `i18n/uk.po`: labels/help новых колонок.

`purchase_stock` сейчас auto-installed при совместной установке `purchase` и `stock_account`, но явная dependency фиксирует контракт на `_get_stock_move_price_unit()` и гарантирует порядок загрузки. Новые модели, ACL, record rules и data XML не нужны.

### 2. Источники истины и значения строки

| Значение | Владелец | Семантика |
|---|---|---|
| Справочная закупочная цена | `product.product.last_purchase_price` | company-dependent, tax-included, после скидки, company currency / base UoM |
| Учётная себестоимость | `product.product.standard_price` | company-dependent; manual source of truth для Standard, valuation-managed для AVCO/FIFO |
| `current_standard_price` | `purchase.order.line` | stored, `copy=False`, снимок `standard_price` в order company на Fill/refresh |
| `valuation_purchase_price` | `purchase.order.line` | non-stored стоимость строки по стандартной valuation-семантике в company currency / base UoM |
| `product_cost_method` | `purchase.order.line` | non-stored technical значение текущего effective `cost_method` для UI и server checks |

`current_standard_price` заполняется для каждой eligible строки независимо от текущего cost method, чтобы смена категории/метода не оставляла поле неопределённым. В UI обе standard-cost колонки видимы только при `product_cost_method == "standard"`. Снимок использует общий `price_snapshot_initialized`; отдельный initialization flag не нужен.

`valuation_purchase_price` вычисляется вызовом стандартного `_get_stock_move_price_unit()` с `conversion_date=line.date_order`. Custom-код не дублирует tax/UoM/currency формулу. Значение может намеренно отличаться от `effective_purchase_price`: первое служит учёту, второе — коммерческой reference/markup логике.

### 3. Fill и расхождение

`action_fill_current_prices()` дополнительно читает `product.with_company(order.company_id).standard_price` и сохраняет его в `current_standard_price`, не меняя продукт, lot или valuation.

`price_update_required` остаётся precision-aware и становится OR трёх условий:

1. snapshot reference purchase price отличается от `effective_purchase_price`;
2. snapshot sales price отличается от `planned_sale_price`;
3. текущий effective cost method равен `standard`, а `current_standard_price` отличается от `valuation_purchase_price`.

Все сравнения используют `float_compare(..., precision_rounding=order.company_id.currency_id.rounding)`. При AVCO/FIFO третье условие всегда ложно. Смена метода после Fill оценивается по текущему effective `cost_method`, а не по историческому методу на момент снимка.

### 4. Одиночное Update

`action_update_product_prices()` повторно проверяет eligibility, initialization, текущий cost method и расхождения server-side. Payload формируется перед product write:

- `last_purchase_price = effective_purchase_price`;
- `lst_price = planned_sale_price`;
- дополнительно `standard_price = valuation_purchase_price`, только если продукт в order company сейчас использует Standard Price.

Запись выполняется на `product.with_company(order.company_id)` обычным ORM от текущего пользователя. Custom `sudo()`, `disable_auto_revaluation`, ручной `product.value` и прямой SQL запрещены. Поэтому стандартный `product.product.write()` сам создаёт cost history и выполняет штатную lot propagation. Одно product write сохраняет атомарность трёх целевых значений.

После успешной записи refresh затронутых eligible строк того же заказа дополнительно обновляет `current_standard_price` из final company-specific product value. Повторный action при отсутствии расхождения является no-op и не создаёт новую cost history.

### 5. Update All и конфликты

Как и в базовом design, candidate payloads полностью фиксируются до первой записи и сортируются по `(order, sequence, id)`. `cost_method` и `valuation_purchase_price` входят в frozen payload: запись другой строки не должна менять решение текущей.

Для повторяющихся строк одного Standard Price продукта последняя candidate line задаёт final `standard_price`. Чтобы одно массовое пользовательское действие не создавало промежуточную cost history для значений, которые немедленно перекрываются, поле `standard_price` включается только в последний payload данного `(company, product)`. Остальные reference/sales payloads применяются в существующем детерминированном порядке. Для разных вариантов `standard_price` остаётся variant-specific, тогда как `lst_price` сохраняет общий template owner базового change.

После всех записей снимки связанных строк refresh-ятся из final product values. Ошибка любой product write или snapshot refresh откатывает reference/sales prices, `standard_price`, созданные стандартным ORM записи `product.value` и lot propagation общей транзакцией.

### 6. Cost method, lifecycle и каналы вызова

- Standard Price: явный line/bulk Update записывает `standard_price`.
- AVCO/FIFO: line/bulk Update записывает только существующие reference/sales targets; cost и lot cost не затрагиваются custom-кодом.
- Confirm, double approval, receipt, bill, cancel, reset, lock/unlock: Price Control не добавляет cost writes; штатные stock/accounting процессы продолжают работать.
- Duplicate: `current_standard_price` очищается через `copy=False` вместе с общим initialization state.
- Import/create/write PO lines: не запускают скрытый cost update.
- API/RPC: вызов тех же public actions имеет те же проверки и side effects, что UI.
- Retry: action с пустым candidate set безопасный no-op; после успешного refresh повтор не создаёт history.

### 7. Права и multi-company

Чтение и запись `standard_price` всегда выполняются через `with_company(order.company_id)`; ambient company не определяет target. Доступность order company должна оставаться в рамках стандартного `allowed_company_ids` пользователя.

Custom actions не используют `sudo()`. Пользователь должен иметь стандартное право записи PO line для Fill/refresh и продукта для Update. Внутренний `sudo()` стандартного `stock_account`, создающий `product.value` и распространяющий lot cost после уже разрешённой product write, не обходится и не дублируется. AccessError или validation error откатывает весь line/bulk action.

### 8. Upgrade и последовательность изменений

После module update Odoo создаёт stored column `current_standard_price`; существующие строки получают `0.0`, но остаются `price_snapshot_initialized=False`, поэтому значение не трактуется как реальный снимок. Backfill и destructive migration не нужны.

Change зависит от целевого состояния `revise-purchase-price-control-actions`. Рекомендуемая последовательность: сначала реализовать и проверить базовый change, затем этот change; либо до первой реализации согласованно перенести требования данного change в базовые artifacts и реализовать единым diff. Самостоятельное применение к текущему confirm-driven коду недопустимо, потому что требование относится к ещё отсутствующим Fill/Update actions.

### 9. Проверка

Focused backend tests должны покрыть:

- valuation price против tax-included reference price для recoverable и cost-bearing taxes;
- discount, purchase UoM, foreign currency и order-date rate;
- Fill/refill и стабильность `current_standard_price`;
- action visibility при cost-only discrepancy и денежную tolerance;
- line Update Standard в draft, confirmed, locked и cancelled состояниях;
- normal `product.value` history и standard lot propagation;
- Update All для разных/одинаковых products, last-line-wins и одну final cost history на product;
- AVCO/FIFO и lot-valuated AVCO/FIFO без custom cost changes;
- смену cost method между Fill и Update;
- multi-company isolation, product permissions и atomic rollback;
- no-op retry, duplicate, import/API и отсутствие confirm/approve/cancel/reset/receipt side effects;
- module update с новым stored column и неинициализированными существующими строками.

Static validation включает Python syntax/imports, manifest dependency, XML/views/translations и module update. По правилам проекта browser tests не создаются и не запускаются; видимость новых колонок и object-buttons проверяется ручным smoke test.

## Risks / Trade-offs

- **Учётный эффект.** Явное изменение `standard_price` способно изменить историю стоимости, оценку Standard Price и стоимость lot-valuated партий. Это требуемый результат, но он существенно сильнее обновления справочной цены.
- **Два разных purchase values.** Пользователь увидит tax-included reference price и valuation-compatible cost; названия/help должны ясно объяснять различие.
- **Метод изменился после Fill.** Решение о cost write принимается по методу на момент Update; сохранённый cost snapshot остаётся базой сравнения до Refill.
- **Закрытые документы.** Базовый change разрешает actions в cancelled/locked PO; значит из исторического документа можно явно изменить текущую учётную стоимость при наличии прав.
- **Одновременное изменение category.** Стандартная транзакционная модель не блокирует внешнюю смену cost method между чтением и write; server-side повторная проверка непосредственно перед payload/write уменьшает риск, а обычная изоляция PostgreSQL остаётся пределом гарантии.
- **Зависимость от незавершённого change.** Реализация требует заранее согласованной последовательности или объединения artifacts.

Отклонённые альтернативы:

- писать tax-included `effective_purchase_price` в `standard_price` — включает возмещаемые налоги и расходится со стандартной valuation-семантикой;
- писать `standard_price` для AVCO/FIFO — создаёт конкурирующий manual valuation input и будет переопределяться складскими алгоритмами;
- обновлять cost при confirm или receipt custom-hook — возвращает скрытые lifecycle side effects и дублирует stock valuation;
- использовать `sudo()` или `disable_auto_revaluation` — обходит права либо штатную cost history/lot propagation;
- не хранить standard-cost snapshot — cost-only discrepancy нельзя согласованно показать и устранить в snapshot-driven UI;
- писать каждое промежуточное standard cost для повторяющегося продукта в bulk — засоряет историю значениями, которые не являются итогом одного пользовательского действия;
- создавать отдельный wizard или persistent history model — избыточно при существующих actions и стандартном `product.value`.
