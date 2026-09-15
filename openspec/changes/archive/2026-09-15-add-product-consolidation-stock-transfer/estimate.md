# Оценка реализации

## Итог

- Всего сценариев: 28
- Implementation-driving сценариев: 14
- Verification-only сценариев: 14
- Implementation clusters: 3
- Implementation units: 15
- Fast path: нет
- Эмпирический размер: large
- Производительность: 1 час на implementation unit
- Базовая оценка: 15 часов
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 14–18 часов активной работы мидл Odoo-разработчика
- Уверенность: средняя

Fast path неприменим: изменение создаёт завершённые stock movements, переносит FIFO value, затрагивает concurrency и требует атомарного failure recovery. Обычные focused tests, static checks, один module update и non-browser smoke включены в clusters.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| product-card-consolidation | Preview transferable stock | implementation-driving | C1 | stock, view-conflict | Нужен новый stock plan и структурированный preview. |
| product-card-consolidation | Consolidate products with positive stock | implementation-driving | C2 | stock, accounting | Требуется парное выбытие/поступление и проверка итоговых количеств. |
| product-card-consolidation | Preserve storage dimensions | implementation-driving | C2 | stock | План и движения должны сохранять location/package. |
| product-card-consolidation | Preserve historical stock reports | verification-only | C2 | stock, accounting | Проверяет текущую дату новых движений и отсутствие historical writes. |
| product-card-consolidation | Consolidate products without stock | verification-only | C2 | regression | Проверяет ветвь существующего поведения без нового движения. |
| product-card-consolidation | Preserve multiple remaining FIFO layer values | implementation-driving | C2 | stock, accounting | Основной механизм разбивает остаток по слоям и переносит фактическую стоимость. |
| product-card-consolidation | Append transferred layers to canonical FIFO | verification-only | C2 | stock, accounting | Следует из текущей даты и порядка создания входящих движений. |
| product-card-consolidation | Record source receipt audit data | implementation-driving | C3 | stock, security | Нужны readonly-связи, snapshot даты и отображение. |
| product-card-consolidation | Warn about mutable source valuation | implementation-driving | C1 | procurement, accounting | Анализ должен выявить незавершённое supplier billing и добавить warning. |
| product-card-consolidation | Reject negative or unreconciled stock | implementation-driving | C1 | stock, accounting | Нужна сверка quant totals с FIFO remaining quantities. |
| product-card-consolidation | Reject stock under inventory counting | verification-only | C1 | stock | Существующая проверка сохраняется и уточняется. |
| product-card-consolidation | Reject open duplicate stock operations | implementation-driving | C1 | stock, procurement | Добавляется state-aware проверка stock moves. |
| product-card-consolidation | Reject unsupported ownership or tracking | implementation-driving | C1 | stock | Добавляется owner dimension; tracking guard уже существует. |
| product-card-consolidation | Revalidate stock before confirmation | implementation-driving | C1 | stock, concurrency | Confirmation перестраивает план из текущих данных. |
| product-card-consolidation | Reject multi-variant templates | verification-only | C1 | regression | Сохраняет существующую eligibility validation. |
| product-card-consolidation | Reject incompatible identity and inventory settings | verification-only | C1 | regression | Сохраняет существующую compatibility matrix. |
| product-card-consolidation | Reject incompatible stock valuation settings | implementation-driving | C1 | stock, accounting | Нужна новая проверка cost method, valuation, location и accounts. |
| product-card-consolidation | Reject tracked products | verification-only | C1 | stock | Проверяет существующий lot/tracking blocker. |
| product-card-consolidation | Reject current stock or reservations | implementation-driving | C1 | stock, concurrency | Прежний общий blocker уточняется: eligible stock разрешён, reservations и unsupported stock блокируются. |
| product-card-consolidation | Accept eligible current stock | verification-only | C1 | stock | Проверяет новую положительную ветвь общего analyzer. |
| product-card-consolidation | Revalidate before confirmation | verification-only | C1 | concurrency | Покрывается полным повторным analyzer вместе со stock revalidation. |
| product-card-consolidation | Reject an unauthorized user | verification-only | C3 | security | Существующая группа и API guard распространяются на новый handler. |
| product-card-consolidation | Confirm an irreversible action | implementation-driving | C3 | security, view-conflict | Требуется точное stock-aware подтверждение в существующем wizard. |
| product-card-consolidation | Cancel before stock transfer | verification-only | C3 | stock | Standard transient cancellation не вызывает service. |
| product-card-consolidation | Record a successful consolidation | implementation-driving | C3 | security | Chatter должен перечислить созданные movements и итог. |
| product-card-consolidation | Roll back a failed consolidation | verification-only | C2 | stock, accounting | Проверяет общую транзакцию и принудительный failure path. |
| product-card-consolidation | Retry after a failed attempt | verification-only | C1 | concurrency | Использует rollback и повторный analyzer без отдельного механизма. |
| product-card-consolidation | Use an ordinary product | verification-only | C2 | regression | Проверяет отсутствие влияния на обычные stock flows. |

Классификация:

- `implementation-driving` — требует нового или изменённого production-поведения;
- `verification-only` — не требует отдельной реализации и проверяет общий механизм, стандартное поведение или отсутствие регрессии.

Каждый Scenario присутствует в таблице ровно один раз.

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Расширенный analyzer: quants, FIFO stack, valuation compatibility, open operations, warnings и повторная проверка | Preview, все stock blockers, valuation compatibility, current-stock acceptance, warnings, revalidation | 5 | Нетривиальное согласование вычисляемой FIFO-оценки с quant dimensions и состояниями Stock/Purchase. |
| C2 | Атомарное создание парных inventory movements, перенос ручной стоимости, блокировки и итоговые инварианты | Quantity transfer, locations/packages, FIFO layers/order, dates, rollback, retry, zero-stock regression | 8 | Основная высокорисковая Stock/Accounting lifecycle-логика с concurrency и failure recovery. |
| C3 | Поля аудита `stock.move`, transient preview fields, inherited views, confirmation и chatter | Source audit, permission boundary, confirmation/cancellation, success audit | 2 | Согласованное небольшое расширение моделей и интерфейса по существующему паттерну. |

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет. Количество, стоимость, место, блокировки и аудит уже разделены на независимо проверяемые эффекты.

### Дублирующиеся или пересекающиеся сценарии

- `Revalidate stock before confirmation` конкретизирует складские значения, а `Revalidate before confirmation` сохраняет общий контракт всей операции. Они используют один analyzer, но защищают разные границы спецификации.
- `Reject unsupported ownership or tracking` и `Reject tracked products` частично пересекаются по tracking. Первый фиксирует ограничения именно переносимого остатка, второй сохраняет прежний общий контракт карточек; реализации отдельного механизма не требуют.

### Недостающие сценарии

- Будущие возвраты и поздняя переоценка намеренно исключены. Snapshot warning покрывает наблюдаемое поведение стоимости на момент объединения.

### Недостаточно определённые или противоречивые сценарии

- Нет. «Compatible FIFO valuation settings» раскрыто в design как одинаковые cost method, valuation mode, inventory adjustment location и stock account mapping.

## Расчёт трудозатрат

- Сумма implementation units: 15
- Hours per unit: 1
- Базовые часы: 15
- Discovery: 0
- Миграция или обработка данных: 0
- Production-like bulk/external coordination/special hardware: 0
- Необычная длительная или ручная проверка: 0
- Другие исключительные конкретные работы: 0
- Итоговый диапазон: 14–18 часов

Диапазон учитывает обычную вариативность вокруг базовых 15 часов. Дополнительный множитель за Stock/Accounting не применяется; риск уже отражён в Units кластера C2.

## Стратегия проверки

### Автоматизированные тесты

- Требуются: да.
- Обоснование: меняются реальные stock quantities, FIFO value, transaction rollback, права и поведение при конкурентном изменении.
- Минимальный набор:
  - 5 + 10 = 15 и zero-stock flow;
  - несколько FIFO receipts, частичное потребление, итоговая quantity/value и порядок canonical layers;
  - location/package preservation;
  - reservation, negative, inventory count, open move, owner, tracking и valuation blockers;
  - source audit и mutable valuation warning;
  - stale preview, forced failure, rollback и retry;
  - authorization, company isolation и ordinary stock regression.

### Module update и smoke verification

- Проверить Python syntax/imports, manifest dependency, XML/external IDs и отсутствие новой ACL gap.
- Обновить `product_card_consolidation` на отдельной тестовой БД и выполнить tagged tests модуля.
- Проверить preview, confirmation text и readonly audit fields компиляцией views и доступным ручным smoke test.
- Browser automation не выполнять по правилам проекта.

## Основные факторы сложности

- FIFO remaining quantities/value вычисляются из истории moves, а физическое размещение хранится отдельно в quants.
- Исходящее движение должно потребить рассчитанный слой, а входящее — получить точно его фактическое значение.
- Между preview и confirmation stock может измениться; операция не должна создать отрицательный quant или частичный перенос.
- Режимы и счета оценки должны гарантировать нейтральность общей стоимости.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| stock | Ошибка количества или dimensions нарушит физический остаток | Только standard moves, повторная сверка, итоговые invariants и multi-location tests |
| accounting | Неверное значение слоя изменит inventory valuation | Фактический out value, manual inbound value, currency-rounded equality tests |
| procurement | Поздний vendor bill может изменить source receipt после snapshot | Preview warning и явное исключение auto-sync |
| concurrency | Stock меняется между preview и confirmation | Повторный analysis, блокировка затронутых quant и полный rollback |
| security | `sudo()` может расширить область складской записи | Existing group, exact company checks и allowlisted records |
| view-conflict | Wizard и stock.move form наследуются в установленной среде | Устойчивые XPath и module update/XML compilation |
| uncertainty | Детали standard valuation inverse и locking требуют runtime подтверждения | Focused characterization tests перед основной реализацией |

## Предположения

- Положительный перенос поддерживается только для совместимых FIFO products без tracking.
- Остаток принадлежит компании, находится в valued internal/transit locations и не зарезервирован.
- Основной товар может иметь собственный остаток; перенесённые слои добавляются после него.
- Стоимость фиксируется на момент подтверждения и не синхронизируется позже.
- Существующее пользовательское изменение автора в manifest будет сохранено при реализации.

## Исключено из оценки

- Lots/serials, lot valuation, FEFO, expiration dates и owner/consignment stock.
- Backdating или переписывание historical documents/moves/account entries.
- Автоматическая обработка будущих возвратов на archived duplicate.
- Late valuation synchronization, landed costs и production data cleanup.
- Реальное выполнение объединений в production и browser automation.

## Требуется discovery

- Нет.
- Обоснование: extension points и основной алгоритм определены. Характеризационная проверка `value_manual`, FIFO stack и quant locking входит в C2.

## Условия пересмотра оценки

- Появится требование сохранять объединённый FIFO по исходным датам.
- Потребуется переносить `stock.lot`, serials, reservations, owners или отрицательный stock.
- Нужно автоматически обрабатывать будущие returns или late valuation changes.
- Разные valuation accounts/categories должны объединяться с отдельными accounting entries.
- Объём одной операции окажется настолько большим, что потребуется асинхронный batch process.

## Фактический результат

Заполняется после реализации:

- Фактические часы:
- Отклонение от оценки:
- Причина отклонения:
- Фактические часы на unit:
- Изменения для будущей калибровки:
