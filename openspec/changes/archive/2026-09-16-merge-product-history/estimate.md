# Оценка реализации

## Итог

- Всего сценариев: 89.
- Implementation-driving сценариев: 26.
- Verification-only сценариев: 63.
- Implementation clusters: 8 рабочих групп; K0 — только регрессионное покрытие, 0 единиц.
- Implementation units: 41.
- Fast path: нет.
- Эмпирический размер: large.
- Производительность: предварительно 1 час на единицу; собственной подтверждённой калибровки для такого преобразования нет.
- Базовая оценка: 41 ч, включая обычные направленные тесты, статические проверки, обновление модулей и проверку основных операций.
- Исключительные дополнительные работы: 4–8 ч проверочного опыта по изменению идентичности и выводу старых пар; 4–6 ч испытания преобразования репрезентативной копии истории и сверки стандартных отчётов.
- Итоговая оценка: **49–55 часов активной работы мидл Odoo-разработчика**, условно при успешном проверочном опыте.
- Уверенность: средняя-низкая до проверки способа вывода старых пар из стандартной оценки.

Это оценка реализации механизма, а не срок автоматического исправления клиентской базы. Рабочие данные этим предложением не преобразуются.

## Покрытие сценариев

Каждый сценарий ниже учтён ровно один раз. Количество сценариев не используется как множитель трудозатрат. Сценарии с префиксом S и исходные сценарии без префикса сохранены из изменяемых требований для проверки отсутствия регрессий и прежнего способа объединения.

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| `pos-cost-recompute` | S01 Select historical orders by filters | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | S02 Recompute a nonzero saved cost | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | S03 Respect explicit order selection | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | S04 Reject a missing or invalid selection scope | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | S40 Process a selection exceeding the former line limit | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | S05 Preview before applying | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | S06 Acknowledge a zero source | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | S07 Report an empty or skipped selection | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-cost-recompute` | C01 Start from a completed merge | implementation-driving | K8 | stock, accounting | Новое поведение указанного общего механизма. |
| `pos-cost-recompute` | C02 Recompute nonzero merged costs | implementation-driving | K8 | stock, accounting | Новое поведение указанного общего механизма. |
| `pos-cost-recompute` | C03 Exclude retired transfer receipts | verification-only | K5 | stock, migration, uncertainty | Проверка общего механизма без отдельной реализации. |
| `pos-cost-recompute` | C04 Reject stale plans | verification-only | K6 | security, bulk | Проверка общего механизма без отдельной реализации. |
| `pos-cost-recompute` | C07 Reject unsupported valuation | verification-only | K8 | stock, accounting | Проверка общего механизма без отдельной реализации. |
| `pos-cost-recompute` | C05 Apply a stock-only plan | implementation-driving | K8 | stock, accounting | Новое поведение указанного общего механизма. |
| `pos-cost-recompute` | C06 Preserve ordinary cost tools | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | S12 Reject insufficient historical stock | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | S13 Validate the subsequent history | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | S14 Reject an unproven valuation path | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | H01 Consume a fully unified receipt history | implementation-driving | K7 | stock | Новое поведение указанного общего механизма. |
| `pos-historical-stock-writeoff` | H02 Explain an unconverted consolidation | implementation-driving | K7 | stock | Новое поведение указанного общего механизма. |
| `pos-historical-stock-writeoff` | H03 Retain quantity safeguards after consolidation | verification-only | K7 | stock | Проверка общего механизма без отдельной реализации. |
| `pos-historical-stock-writeoff` | S25 Recompute from the earliest of multiple transfers | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | S26 Apply stock costs before POS costs | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | S27 Preserve manual control without pending markers | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | S28 Reject stale or unsupported manual recomputation | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `pos-historical-stock-writeoff` | H04 Include earlier costs affected by a merge | implementation-driving | K8 | stock, accounting | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M01 Preview a new pair | implementation-driving | K1 | view-conflict | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M02 Open conversion from an archived source | implementation-driving | K1 | view-conflict | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M03 Reject invalid identities | implementation-driving | K2 | stock, accounting | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M04 Select and confirm a consolidation mode | implementation-driving | K1 | view-conflict | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M30 Preserve existing callers | verification-only | K1 | — | Проверка совместимости прежнего программного входа. |
| `product-card-consolidation` | Preview an eligible pair | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject an invalid selection count | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Cancel before confirmation | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | M05 Reject incompatible inventory identity | implementation-driving | K2 | stock, accounting | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M06 Reject incomplete operational coverage | implementation-driving | K2 | stock, accounting | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M07 Preserve protected financial history | implementation-driving | K2 | stock, accounting | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M08 Reject cross-company history | implementation-driving | K2 | stock, accounting | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | Reject multi-variant templates | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject incompatible identity and inventory settings | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject incompatible stock valuation settings | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject tracked products | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject current stock or reservations | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Accept eligible current stock | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Revalidate before confirmation | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | M09 Transfer completed and cancelled references | implementation-driving | K3 | stock, procurement | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M10 Preserve editable document values | verification-only | K3 | stock, procurement | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | M11 Preserve prior audit evidence | implementation-driving | K6 | security, bulk | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | Redirect eligible draft documents | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Preserve non-draft history | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Open historical source product | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | M12 Reject unauthorized mutation | implementation-driving | K6 | security, bulk | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M13 Cancel before confirmation | verification-only | K1 | view-conflict | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | M14 Reject a stale or competing confirmation | implementation-driving | K6 | security, bulk | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M15 Roll back a failed merge | verification-only | K6 | security, bulk | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | M16 Reuse the applied result | implementation-driving | K6 | security, bulk | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M26 Protect applied evidence | implementation-driving | K6 | security, bulk | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M27 Retry after a rolled-back failure | verification-only | K6 | security, bulk | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | Reject an unauthorized user | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Confirm an irreversible action | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Cancel before stock transfer | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Record a successful consolidation | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Roll back a failed consolidation | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Retry after a failed attempt | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Preview transferable stock | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Consolidate products with positive stock | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Preserve storage dimensions | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Preserve historical stock reports | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Consolidate products without stock | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Preserve multiple remaining FIFO layer values | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Append transferred layers to canonical FIFO | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Record source receipt audit data | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Warn about mutable source valuation | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject negative or unreconciled stock | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject stock under inventory counting | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject open duplicate stock operations | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Reject unsupported ownership or tracking | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | Revalidate stock before confirmation | verification-only | K0 | — | Сохранение прежнего режима переноса текущего остатка. |
| `product-card-consolidation` | M17 Combine original receipts | implementation-driving | K3 | stock, procurement | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M18 Reconcile physical stock | implementation-driving | K4 | stock | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M19 Keep recomputation manual | verification-only | K3 | stock, procurement | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | M20 Merge another duplicate later | verification-only | K2 | stock, accounting | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | M28 Consolidate compatible cards without stock history | verification-only | K2 | stock, accounting | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | M21 Preserve ordinary behavior | verification-only | K0 | — | Сохраняемое поведение существующего инструмента. |
| `product-card-consolidation` | M22 Convert an existing transfer | implementation-driving | K5 | stock, migration, uncertainty | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M23 Reject an unproven old transfer | implementation-driving | K5 | stock, migration, uncertainty | Новое поведение указанного общего механизма. |
| `product-card-consolidation` | M24 Upgrade without rewriting history | verification-only | K5 | stock, migration, uncertainty | Проверка общего механизма без отдельной реализации. |
| `product-card-consolidation` | M29 Add a stock-only source after full consolidation | implementation-driving | K7 | stock | Проверка актуального состава источников после применения другого режима. |
| `product-card-consolidation` | M25 Convert all old sources of one target | implementation-driving | K2 | stock, accounting | Новое поведение указанного общего механизма. |

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| K1 | Выбор двух способов и вход из архивного товара | M01, M02, M04, M30, M13 | 3 | Существующий мастер и предпросмотр; сохранение прежнего пути, выбор режима и расширение отбора. |
| K2 | Полная группа и проверка покрытых связей | M03, M05, M06, M07, M08, M20, M28, M25 | 5 | Реестр обработчиков, компании всей истории, финансовые и операционные препятствия. |
| K3 | Согласованная замена идентичности документов и движений | M09, M10, M17, M19 | 8 | Закрытое преобразование завершённых ссылок; инварианты, зависимые значения и сохранение исходных документов. |
| K4 | Согласование физических остатков | M18 | 5 | Объединение стандартных остатков по измерениям и сверка с движениями без новых проводок склада. |
| K5 | Преобразование старых служебных пар | C03, M22, M23, M24 | 8 | Проверка происхождения, исключение пары из действующего учёта, стандартного FIFO и отчётов с сохранением свидетельств. |
| K6 | Защищённый аудит, транзакция и конкуренция | C04, M11, M12, M14, M15, M16, M26, M27 | 5 | Постоянные записи, ACL, приватный контракт, повторные вызовы и ревизии состава истории. |
| K7 | Допуск объединённой истории к историческому списанию | H01, H02, H03, M29 | 2 | Замена общего запрета доказательством полной конверсии; сохранение остальных проверок. |
| K8 | Ручной пересчёт объединённой истории | C01, C02, C07, C05, H04 | 5 | Расширение существующего отбора, ранняя граница, повторное использование складского плана и пересчёта POS. |
| K0 | Сохраняемые стандартные режимы | Сценарии с K0 в таблице покрытия | 0 | Независимой новой реализации нет; проверяются затронутыми регрессионными тестами. |

Стандартный FIFO, существующий мастер, обработчики конфигурации и кодов, исторический складской план и `pos.cost.recompute` повторно используются. Их базовая разработка не посчитана заново. Версии, manifest и число файлов не создают отдельные группы. В K5 включён код преобразования, в дополнительных часах — только отдельный опыт и испытание на репрезентативных данных; двойного подсчёта реализации нет.

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

Отказ устаревшего пересчёта отделён от неподдерживаемой оценки. Повтор применённой операции отделён от защиты аудита; повтор после ошибки — от отката. Остальные совмещённые проверки относятся к инвариантам одной атомарной операции.

### Дублирующиеся или пересекающиеся сценарии

Старые сценарии сохранены с явным условием режима переноса остатка; новые проверяют полную историю. Это намеренное разделение двух способов. Объединение исходных приходов, историческое списание и ручной пересчёт используют общие данные примера, но проверяют разные пользовательские действия. Граница раннего пересчёта из исторического списания относится к K8 и не посчитана вторым механизмом. Регрессионные сценарии сохранены в полностью заменяемых требованиях намеренно.

### Недостающие сценарии

Для заявленного ограниченного профиля не выявлены. Неизвестные операционные связи и непокрытые возвраты дают полный отказ. Расширение на новые виды связей требует дополнительных сценариев и пересмотра оценки.

### Недостаточно определённые или противоречивые сценарии

Наблюдаемый результат определён. Техническое представление выведенной пары требует проверочного опыта, описанного в design.md. Исключение старой служебной пары из требования сохранения состояний указано явно. Объединение не обещает неизменность вычисляемой оценки FIFO после слияния последовательностей.

## Расчёт трудозатрат

- Сумма implementation units: 41.
- Hours per unit: 1.
- Базовые часы: 41.
- Discovery: 4–8 ч — выполненные строки и обе стороны служебной пары в стандартных остатках, FIFO и отчётах Odoo 19.
- Миграция или обработка рабочих данных: 0 ч, не выполняется автоматически и не входит в реализацию.
- Production-like проверка: 4–6 ч — изолированная репрезентативная история нескольких старых источников, сравнение документов, количеств и отчётов до/после.
- Другие исключительные работы: 0 ч.
- Итог: 49–55 ч. Коэффициентов за количество модулей и сценариев нет.

Обычные серверные тесты, XML, обновление модулей и проверка основных операций входят в 41 ч; они не прибавлены повторно. Дополнительная проверка относится к историческому преобразованию на репрезентативных данных, а не к каждому сценарию отдельно.

## Стратегия проверки

### Автоматизированные тесты

Требуются из-за изменения завершённых складских и коммерческих ссылок. Минимум: единая хронология 20+100, преобразование пары 96, несколько источников, суммы и состояния документов, количественные измерения, неизменяемый аудит, отказ на защищённых связях, права/RPC, конкуренция с новыми строками, откат и повтор, историческое списание 31, ручной пересчёт ранних и ненулевых расходов. Проверки через серверный Odoo и стандартный FIFO; браузерная автоматизация запрещена.

### Module update и smoke verification

Обновление затронутых модулей на `odoo_tire_testing`, компиляция XML, проверка установки через `tire`, русский интерфейс мастера и ручного пересчёта. При обновлении ссылки и старые движения не меняются. Обычные товары, импорт старых кодов и прежние режимы пересчёта проверяются регрессионно. Автоматическая проверка браузера не выполняется.

## Основные факторы сложности

Изменение идентичности завершённых строк без повторного проведения; согласование товарных ссылок и остатков; вывод старых пар из всех стандартных выборок; защита финансовой истории; конкурентное появление новых записей; согласование проектных запретов с узким доверенным преобразованием.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| stock | Расхождение движений и остатков | Сверка измерений, исходных дат, стандартного FIFO и количественных отчётов |
| procurement | Изменение связанных коммерческих полей | Снимки цены, налога, количества, сумм и связей закупок/продаж |
| accounting | Попытка переписать защищённую финансовую историю | Полный отказ до записи; отдельные тесты закрытых периодов и связанных счетов |
| migration | Старые переносы и несколько источников | Явная конверсия всей группы, сохранение аудита, обновление без обработки данных |
| security | Обход защит и подделка результата | ACL, правила компании, приватный контракт, проверки RPC и копирования |
| bulk | Неполная выборка и конкурентные вставки | Ревизии состава, полный охват, блокировки и репрезентативная проверка |
| uncertainty | Нет готового стандартного действия для конверсии | Проверочный опыт перед основными изменениями |

## Предположения

Товары действительно являются дублями. Основной профиль — одна компания, одинаковые единицы, отсутствие партий/серий, FIFO и периодическая оценка, известные связи установленного проекта. Текущий исторический инструмент доступен как основа; его не реализуют заново. Состояние старых связей достаточно для доказуемой конверсии либо операция отказывает с конкретной причиной.

## Исключено из оценки

Переписывание проведённых бухгалтерских документов, производство, партии/серии, межфирменное объединение, восстановление потерянных данных, ручная очистка клиентской базы, универсальный обратный процесс, автоматический пересчёт, браузерные тесты, установка зависимостей и внедрение неизвестных сторонних интеграций.

## Требуется discovery

Да: узкий опыт на тестовой базе для подтверждения, что выбранный способ смены идентичности и отмены исключительно служебных пар сохраняет трассируемость и исключает пары из стандартных расчётов. В proposal и design это условие уже раскрыто. Общего этапа «изучить проект» в будущие задачи не переносится.

## Условия пересмотра оценки

Невозможность согласовать отменённые пары со стандартным Odoo; обязательность новых обработчиков защищённых корректировок или финансовых связей; новые виды складских историй; отсутствующие доказательства старого объединения; иной состав установленных модулей; необходимость объединения истории нескольких компаний.

## Фактический результат

Заполняется после реализации: фактические часы, отклонение, причина и часы на единицу. Реализация пока не начата; результатов исполнения или тестов нет.
