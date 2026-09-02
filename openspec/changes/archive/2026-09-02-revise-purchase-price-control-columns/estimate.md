# Оценка реализации

## Итог

- Всего сценариев: 61
- Implementation-driving сценариев: 18
- Verification-only сценариев: 43
- Implementation clusters: 7
- Implementation units: 12
- Fast path: нет — есть версионная миграция сохранённых снимков и запись Standard Price с бухгалтерскими последствиями
- Эмпирический размер: medium
- Производительность: 1 час на implementation unit
- Базовая оценка: 12 часов
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 10–15 часов активной работы мидл Odoo-разработчика
- Уверенность: средне-высокая

Оценка включает сфокусированные серверные тесты, статические проверки, одно обновление модуля и небраузерную проверку формы. Отдельное discovery не требуется: существующий addon и стандартные extension points Odoo 19 проверены.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| purchase-price-control | Display the required columns in order | implementation-driving | C1 | view | Требует изменить XML, подписи и порядок |
| purchase-price-control | Do not add price columns to non-product lines | verification-only | C1 | view | Проверяет существующие invisible-условия |
| purchase-price-control | Ignore purchase tax in price-control calculations | implementation-driving | C2 | tax boundary | Требует исключить налоговый движок из базы |
| purchase-price-control | Apply discount without applying tax | implementation-driving | C2 | price formula | Определяет новую формулу базы |
| purchase-price-control | Convert purchase unit and currency | implementation-driving | C2 | UoM, currency | Сохраняет преобразования без stock helper |
| purchase-price-control | Recalculate an existing snapshot markup | implementation-driving | C6 | migration | Требует воспроизводимую post-migration |
| purchase-price-control | Preserve business records during upgrade | verification-only | C6 | migration safety | Проверяет границы той же миграции |
| purchase-price-control | Display markup based on a saved reference price | implementation-driving | C3 | semantic change | Сохраняет идентификатор сценария, но меняет основу на Current Cost |
| purchase-price-control | Use the default markup without a reference price | implementation-driving | C3 | fallback | Меняет fallback относительно Current Cost |
| purchase-price-control | Display initialized price-control information in any state | verification-only | C3 | lifecycle | Проверяет сохранение существующей доступности |
| purchase-price-control | Ignore non-product lines | verification-only | C3 | eligibility | Покрывается существующим eligibility helper |
| purchase-price-control | Round upward to a whole-price step | implementation-driving | C2 | rounding | Подключает новую базу к существующему округлению |
| purchase-price-control | Preserve an exact multiple | verification-only | C2 | rounding | Проверяет тот же механизм округления |
| purchase-price-control | Round upward to a fractional step | verification-only | C2 | rounding | Проверяет тот же механизм округления |
| purchase-price-control | Enter a planned sales price directly | verification-only | C2 | inverse | Существующий ручной режим не меняется |
| purchase-price-control | Preserve a manual price after the purchase-price basis changes | verification-only | C2 | inverse | Проверяет существующее отделение manual override |
| purchase-price-control | Ignore a tax change | verification-only | C2 | dependency | Проверяет отсутствие `tax_ids` в вычислении |
| purchase-price-control | Restore automatic calculation explicitly | verification-only | C2 | reset | Проверяет существующий Fill с новой базой |
| purchase-price-control | Keep automatic calculation when manual entry is not used | verification-only | C2 | compute | Проверяет новую базу через общий compute |
| purchase-price-control | Do not calculate from an absent snapshot | verification-only | C3 | initialization | Существующий guard сохраняется |
| purchase-price-control | Fill a standard-cost snapshot | implementation-driving | C3 | snapshot | Меняет состав и источники снимка |
| purchase-price-control | Keep the standard-cost snapshot stable | verification-only | C3 | persistence | Проверяет stored-семантику Current Cost |
| purchase-price-control | Fill snapshots for an order | implementation-driving | C3 | batch | Меняет пакетный Fill для всех строк |
| purchase-price-control | Derive markup from filled prices | verification-only | C3 | formula | Проверяет общий механизм снимка |
| purchase-price-control | Use default markup while filling without a reference price | verification-only | C3 | fallback | Проверяет общий fallback снимка |
| purchase-price-control | Fill from the order company | implementation-driving | C3 | multi-company | Новая cost-база требует company context |
| purchase-price-control | Keep a snapshot stable | verification-only | C3 | persistence | Существующая stored-семантика сохраняется |
| purchase-price-control | Refresh an existing snapshot | implementation-driving | C3 | refresh | Fill должен записывать новые источники |
| purchase-price-control | Save an explicitly selected line | implementation-driving | C4 | cost write | Меняет payload явного действия |
| purchase-price-control | Do not save an unselected line | verification-only | C4 | lifecycle | Проверяет явность действий |
| purchase-price-control | Confirmation enters approval workflow | verification-only | C4 | approval | Стандартный approval не меняется |
| purchase-price-control | Multiple selected lines target the same sales-price owner | verification-only | C5 | conflict | Проверяет существующий порядок payload |
| purchase-price-control | Failed confirmation is atomic | verification-only | C4 | rollback | Подтверждение отделено от price control |
| purchase-price-control | Confirm without a standard-cost side effect | verification-only | C4 | lifecycle | Проверяет отсутствие неявной cost-записи |
| purchase-price-control | Confirm an order without a price side effect | verification-only | C4 | lifecycle | Проверяет отсутствие неявной sales-записи |
| purchase-price-control | Complete double validation without a price side effect | verification-only | C4 | approval | Проверяет тот же lifecycle invariant |
| purchase-price-control | Show the line action for a discrepancy | implementation-driving | C4 | discrepancy | Меняется набор сравниваемых значений |
| purchase-price-control | Offer Update for only a standard-cost discrepancy | implementation-driving | C4 | cost method | Требует новую tax-independent cost comparison |
| purchase-price-control | Update a Standard Price product from one line | implementation-driving | C4 | accounting | Записывает новую cost-базу стандартным полем |
| purchase-price-control | Do not write AVCO or FIFO cost | verification-only | C4 | valuation | Проверяет существующую изоляцию методов |
| purchase-price-control | Retry after a successful standard-cost update | verification-only | C4 | retry | Покрывается refresh и discrepancy |
| purchase-price-control | Update both product prices from one line | verification-only | C4 | payload | Покрывается тем же line payload |
| purchase-price-control | Hide the line action without a usable discrepancy | verification-only | C4 | visibility | Обратная проверка общего discrepancy |
| purchase-price-control | Update standard costs in bulk | implementation-driving | C5 | bulk | Требует адаптировать существующий bulk payload |
| purchase-price-control | Resolve repeated Standard Price products deterministically | verification-only | C5 | conflict | Существующий порядок строк сохраняется |
| purchase-price-control | Roll back a failed standard-cost bulk update | verification-only | C5 | atomicity | Проверяет стандартную транзакцию |
| purchase-price-control | Update all differing lines | verification-only | C5 | bulk | Покрывается тем же bulk payload |
| purchase-price-control | Resolve shared price owners deterministically | verification-only | C5 | conflict | Покрывается существующим порядком строк |
| purchase-price-control | Roll back a failed bulk update | verification-only | C5 | atomicity | Проверяет стандартную транзакцию |
| purchase-price-control | Cancel a confirmed order | verification-only | C4 | cancellation | Жизненный цикл не меняется |
| purchase-price-control | Confirm again after resetting to draft | verification-only | C4 | retry lifecycle | Жизненный цикл не меняется |
| purchase-price-control | Update prices from a non-draft order | verification-only | C4 | state | Existing action state-independence сохраняется |
| purchase-price-control | Copy a purchase order | verification-only | C3 | copy | `copy=False` и initialization уже реализованы |
| purchase-price-control | User cannot update an affected product | verification-only | C4 | access, rollback | `sudo()` не добавляется; проверка регрессии |
| purchase-price-control | Keep standard cost company-specific | implementation-driving | C3 | multi-company | Новая cost-based семантика требует company context |
| purchase-price-control | User cannot update the product | verification-only | C4 | access | Сохраняет исходный permission scenario |
| purchase-price-control | Reject an unauthorized standard-cost update | verification-only | C4 | access, rollback | Проверяет тот же ORM write без `sudo()` |
| purchase-price-control | User cannot fill an affected line | verification-only | C3 | access | Стандартная ORM-проверка сохраняется |
| purchase-price-control | Preserve AVCO cost behavior | verification-only | C4 | valuation | Дублирует проверку cost-method guard |
| purchase-price-control | Preserve FIFO cost behavior | verification-only | C4 | valuation | Дублирует проверку cost-method guard |
| purchase-price-control | Preserve standard cost consequences | verification-only | C4 | accounting | Проверяет стандартный `standard_price` write |

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Узкое наследование list-формы, подписи, порядок и переводы | 1–2 | 1 | Несколько согласованных XML/translation изменений в одном view |
| C2 | Налогонезависимая база и вычисление `New Sale` | 3–5, 12–20 | 2 | Нетривиальная формула со скидкой, UoM, валютой и depends |
| C3 | Cost-based снимок, наценка, Fill и company context | 8–11, 21–28, 53, 55, 58 | 2 | Согласованное поведение заказа и строк внутри одного addon |
| C4 | Line Update, discrepancy и Standard/AVCO/FIFO boundary | 29–43, 50–52, 54, 56–57, 59–61 | 2 | Адаптация существующего явного action и cost payload |
| C5 | Bulk payload, конфликты и атомарность | 32, 44–49 | 1 | Основной bulk-механизм уже существует, меняется состав payload |
| C6 | Версионная миграция сохранённой наценки | 6–7 | 3 | Stored-семантика меняется на установленных базах, нужна batch/company-safe миграция |
| C7 | Удаление legacy reference/tax fields | REMOVED requirements | 1 | Локальная очистка модели, столбцов, импортов, зависимостей и upgrade-проверка |

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет.

### Дублирующиеся или пересекающиеся сценарии

- `Do not write AVCO or FIFO cost` пересекается с отдельными `Preserve AVCO cost behavior` и `Preserve FIFO cost behavior`, но первая проверяет line action, а последние сохраняют каноническую границу оценки запасов для line и bulk.
- `Display markup based on a saved reference price` сохраняет историческое имя сценария для совместимости OpenSpec, но его обновлённое содержание и `Derive markup from filled prices` проверяют cost-based правило на уровнях интерфейса и снимка.

### Недостающие сценарии

- Нет: отдельно покрыты миграция, ненулевой налог при налогонезависимой логике, Standard/AVCO/FIFO, компании, права, lifecycle, copy, retry и rollback.

### Недостаточно определённые или противоречивые сценарии

- Предполагается, что скидка остаётся частью закупочной базы, поскольку пользователь исключил только добавленную налоговую семантику.
- Для отличающихся валют и единиц `Unit Price` остаётся стандартным отображаемым значением строки, а `New Sale` рассчитывается в валюте компании за базовую единицу товара; это явно закреплено в design.

## Расчёт трудозатрат

- Сумма implementation units: 12
- Hours per unit: 1 час
- Базовые часы: 12
- Discovery: 0 часов
- Миграция или обработка данных: 0 дополнительных часов; включена в C6
- Production-like bulk/external coordination/special hardware: 0 часов
- Необычная длительная или ручная проверка: 0 часов
- Другие исключительные конкретные работы: 0 часов
- Итоговый диапазон: 10–15 часов

Оценка изменится, если потребуется архивировать legacy-значения, обновлять `tax_ids`, пересчитывать товары или бухгалтерские/складские записи, либо распространить интерфейс на другие формы помимо стандартной формы заказа закупки.
