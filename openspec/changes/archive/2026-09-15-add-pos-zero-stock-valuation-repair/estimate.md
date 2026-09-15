# Оценка реализации

## Итог

- Всего сценариев: **38** (27 новых и 11 сохранённых в изменяемых требованиях).
- Implementation-driving сценариев: **16**.
- Verification-only сценариев: **22**.
- Implementation clusters: **5**.
- Implementation units: **25**.
- Fast path: нет; меняются складская оценка, постоянная история и конкурентное применение.
- Эмпирический размер: large.
- Производительность: ориентир 1 час мидл Odoo-разработчика на единицу; собственной калибровки нет.
- Базовая оценка: **25 часов** с профильными тестами и обычной проверкой поставки.
- Исключительные дополнительные работы: 0 часов; D1/D2 включены в C3/C4, не прибавлены повторно.
- Итоговая оценка: **24–32 часа**, с согласованным общим контролем версий источников.
- Уверенность: средняя в объёме; ограниченная в безопасном способе фиксации исторического значения и протоколе конкуренции.

Это активное время мидл-разработчика, не срок выполнения агентом. Обычные тесты, статические проверки, одно обновление и ручная проверка доступной формы входят в механизмы. Исследование первых D1/D2 следует выполнить до зависимой реализации; при необходимости нового движка оценки текущий диапазон недействителен.

## Покрытие сценариев

`implementation-driving` обозначает новое поведение; `verification-only` — вариант общего механизма, сохранённое или стандартное поведение без отдельной реализации. Единицы назначены только механизмам ниже.

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| pos-cost-recompute | S25 Apply a reviewed mixed selection | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-cost-recompute | S26 Reject stale preview data | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-cost-recompute | S27 Roll back a runtime failure | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-cost-recompute | S28 Retry or concurrently submit the same operation | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-cost-recompute | S29 Reject overlapping stale operations | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-cost-recompute | S30 Cancel before application | verification-only | C1 | stock | Общие поля, просмотр, итоги и подтверждение существующей операции |
| pos-cost-recompute | S31 Recompute again with unchanged inputs | verification-only | C3 | stock, accounting, uncertainty | Фиксированная запись и сохранение результата при стандартных действиях |
| pos-cost-recompute | S36 Refresh standard POS margin reporting | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-cost-recompute | S37 Preserve invoiced order accounting and stock | verification-only | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-cost-recompute | S38 Preserve ordinary workflows | verification-only | C3 | stock, accounting, uncertainty | Фиксированная запись и сохранение результата при стандартных действиях |
| pos-cost-recompute | S39 Install and upgrade without recomputation | verification-only | C5 | security, migration | Общая защита доступа, истории и совместимости старых операций |
| pos-zero-stock-valuation-repair | R01 Choose stock repair explicitly | implementation-driving | C1 | stock | Общие поля, просмотр, итоги и подтверждение существующей операции |
| pos-zero-stock-valuation-repair | R02 Preserve nonzero stock values | verification-only | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R03 Repair an issue against its sole earlier receipt | implementation-driving | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R04 Ignore a more expensive later receipt | verification-only | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R05 Account for earlier consumption | verification-only | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R06 Reject an ambiguous or invalid source | implementation-driving | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R07 Require complete POS coverage of an issue | implementation-driving | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R08 Reject financial dependencies | implementation-driving | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R09 Reject dependent or unsupported stock history | verification-only | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R10 Explain a costing-method change | implementation-driving | C1 | stock | Общие поля, просмотр, итоги и подтверждение существующей операции |
| pos-zero-stock-valuation-repair | R11 Preview without operational effects | verification-only | C1 | stock | Общие поля, просмотр, итоги и подтверждение существующей операции |
| pos-zero-stock-valuation-repair | R12 Review totals and currencies | implementation-driving | C1 | stock | Общие поля, просмотр, итоги и подтверждение существующей операции |
| pos-zero-stock-valuation-repair | R13 Require stock-specific acknowledgement | implementation-driving | C1 | stock | Общие поля, просмотр, итоги и подтверждение существующей операции |
| pos-zero-stock-valuation-repair | R14 Warn about unsettled receipt valuation | implementation-driving | C2 | stock, accounting | Общий анализ источника и серверных условий допуска |
| pos-zero-stock-valuation-repair | R15 Reject changed evidence | implementation-driving | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-zero-stock-valuation-repair | R16 Roll back a stock repair followed by POS failure | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-zero-stock-valuation-repair | R17 Protect the audit evidence | implementation-driving | C5 | security, migration | Общая защита доступа, истории и совместимости старых операций |
| pos-zero-stock-valuation-repair | R18 Preserve the reviewed amount on later valuation calls | implementation-driving | C3 | stock, accounting, uncertainty | Фиксированная запись и сохранение результата при стандартных действиях |
| pos-zero-stock-valuation-repair | R19 Serialize overlapping repairs | verification-only | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-zero-stock-valuation-repair | R25 Return goods after a completed repair | verification-only | C3 | stock, accounting, uncertainty | Фиксированная запись и сохранение результата при стандартных действиях |
| pos-zero-stock-valuation-repair | R20 Deny a POS manager without stock permission | implementation-driving | C5 | security, migration | Общая защита доступа, истории и совместимости старых операций |
| pos-zero-stock-valuation-repair | R21 Reject cross-company evidence | verification-only | C5 | security, migration | Общая защита доступа, истории и совместимости старых операций |
| pos-zero-stock-valuation-repair | R22 Upgrade safely | implementation-driving | C5 | security, migration | Общая защита доступа, истории и совместимости старых операций |
| pos-zero-stock-valuation-repair | R27 Copy repair criteria without applied effects | verification-only | C5 | security, migration | Общая защита доступа, истории и совместимости старых операций |
| pos-zero-stock-valuation-repair | R23 Keep later receipt changes explicit | verification-only | C3 | stock, accounting, uncertainty | Фиксированная запись и сохранение результата при стандартных действиях |
| pos-zero-stock-valuation-repair | R24 Apply a reviewed mixed selection | implementation-driving | C4 | bulk, stock, uncertainty | Единый протокол снимка, блокировок и применения stock/POS |
| pos-zero-stock-valuation-repair | R26 Preserve evidence on module removal | implementation-driving | C5 | security, migration | Общая защита доступа, истории и совместимости старых операций |

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Режим, складская детализация просмотра, итоги и подтверждение | R01, R10–R13, S30 | 3 | Расширяются готовые формы/снимки; одна строка истории на движение, стандартная отмена переиспользуется |
| C2 | Однозначный источник и полный анализ допуска | R02–R09, R14, S37 | 5 | Пакетное чтение исторических движений, достаточность количества, полнота выбора и финансовые ограничения; без нового FIFO |
| C3 | Фиксированная оценка и последующий стандартный жизненный цикл | R18, R23, R25, S31, S38 | 8 | Узкий сервис ORM и защита от сегодняшнего FIFO, D1, дальнейший возврат и обычные движения |
| C4 | Атомарный переход от stock plan к POS, снимки и блокировки | R15, R16, R19, R24, S25–S29, S36 | 7 | Общая транзакция, D2 и согласованный контроль версий в путях изменения источников; независимые подключения, смешанный набор, откат и нагрузочная регрессия |
| C5 | Права, неизменяемость, копирование и обновление | R17, R20–R22, R26, R27, S39 | 2 | Переиспользуются объектный токен и правила компаний; новый ACL, безопасные значения старых записей и запрет удаления с историей |

Сумма: 3 + 5 + 8 + 7 + 2 = **25**. Готовые базовый пересчёт, стандартный расчёт POS, ORM, формы и тестовые помощники снижают объём. Новая модель, версия и число файлов не оцениваются отдельно. Механизма на 13 единиц нет: две конкретные неопределённости выделены как ранние проверки D1/D2 внутри соответствующих механизмов.

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

R06/R08/R09 описывают варианты единой проверки допуска; проверяются параметризованно. Безопасное обновление R22 и копирование R27 разделены на самостоятельные сценарии одного механизма совместимости.

### Дублирующиеся или пересекающиеся сценарии

R16 уточняет откат склада относительно сохранённого S27; R19 уточняет stock-конфликт относительно S28/S29; R24 расширяет S25. Они относятся к C4, повторных единиц нет. Остальные сохранённые S-сценарии проверяют базовую совместимость; независимой разработки для каждого нет.

### Недостающие сценарии

В заявленной первой версии не обнаружены. Добавлены будущий обычный возврат R25 и сохранение истории при удалении модуля R26; отмена/повтор/стандартные продажи сохранены из базового требования.

### Недостаточно определённые или противоречивые сценарии

Исходный запрет менять stock value явно ограничен обычным режимом в delta `pos-cost-recompute`; база должна быть синхронизирована первой. Бизнес-результат фиксирован, техническая реализуемость узкого setter и защиты от конкурентно добавленных источников остаётся предметом D1/D2. Историческая закупочная цена не обещана: receipt value является текущим снимком с предупреждением.

## Расчёт трудозатрат

- Сумма implementation units: 25.
- Hours per unit: 1.
- Базовые часы: 25.
- Discovery: 0 дополнительных; D1 в C3, D2 в C4.
- Миграция/очистка рабочих данных: 0; массовое применение не входит в поставку.
- Особые внешние системы/оборудование: 0.
- Необычная длительная ручная проверка: 0; обычная проверка формы включена.
- Другие исключительные работы: 0.
- Итоговый диапазон: 24–32 часа с согласованным протоколом контроля версий.

Нет дополнительного множителя за stock/accounting/security. Исправление фактических рабочих документов и устранение неизвестных финансовых зависимостей не включены скрыто в оценку.

## Стратегия проверки

### Автоматизированные тесты

Обязательны из-за изменения исторической оценки и известного расхождения стандартного setter. Минимум: исходный пример 814,46; позднее поступление 900; предшествующий расход; неприменимые источники; неизменность количества/дат/остатков/receipt/product costs; будущий возврат; защита записи и истории; конкуренция двух подключений; полный откат после первого stock write; смешанный набор; компании и роли; старые ready/done операции; повторное обновление и блокировка удаления с применёнными ремонтами. Использовать существующую инфраструктуру, без браузерных тестов.

### Module update и smoke verification

Python/XML/ACL/manifest/external-ID проверки, установка/повторное обновление на `odoo_tire_testing` с реальным addons_path и портом 8077, базовый набор `pos_cost_recompute` и профильная стандартная регрессия stock/POS. Ручная проверка режима и подтверждений при доступности; отсутствие такой проверки явно отметить. Зависимости и инструменты не устанавливать.

## Основные факторы сложности

Защита фиксированной исторической оценки от стандартной текущей FIFO-переоценки, доказательство полноты исторических источников, связь нескольких POS-строк с движением, блокировки новых ссылок и совместимость сохранённых операций.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| stock | Неверная оценка или повторный расход | Только один доказуемый receipt, неизменность количества и тест с поздней ценой |
| accounting | Противоречие уже признанным суммам | Отказ для проводок, аналитических записей, счетов и заблокированного периода |
| security | Подмена применённой оценки или источника | Пересечение прав, защищённые связи и токен, прямые запросы |
| bulk | Двойная запись общего движения или частичный результат | Уникальный stock plan, полный охват, общая транзакция |
| migration | Изменение старых операций или потеря аудита | Режим False для старых записей, обновление без ремонта, проверка удаления |
| uncertainty | Узкий безопасный setter/блокировки могут оказаться недостаточны | D1/D2 до зависимой реализации, пересмотр оценки вместо обхода ограничений |

## Предположения

Базовый модуль и разрешённая тестовая база доступны; текущая установленная версия Odoo соответствует исследованной. Первая версия ограничена прямыми списаниями с одним предшествующим receipt. Периодические финансовые последствия должны быть доказуемо исключены. Для обычного пересчёта не требуется stock manager.

## Исключено из оценки

Универсальный исторический FIFO/AVCO, бухгалтерские корректировки, автоматическая переоценка последующих возвратов, интеграции, фоновые очереди, установка компонентов, исправление всех рабочих документов и завершение чужих незакрытых OpenSpec-изменений.

## Требуется discovery

Да, две конкретные проверки из design: D1 — последствия/устойчивость фиксированной записи; D2 — конкуренция новых исторических/финансовых ссылок. Предыдущее исследование уже доказало причину нуля и опасность текущего FIFO, поэтому повторять общее исследование не нужно. Труд этих проверок включён в механизмы.

## Условия пересмотра оценки

Несколько исходных receipts; необходимость менять проводки или создавать общий движок переоценки; неустранимый узкими средствами конфликт со стандартным изменением складских записей; большие истории, требующие фоновой обработки; иной контракт будущих возвратов; недоступность разрешённой тестовой среды.

## Фактический результат

Реализация завершена 15.09.2026. После согласования общей координации источников
C4 увеличен с 5 до 7 единиц, общая оценка — с 23 до 25 единиц и с 22–30 до
24–32 часов. Это оценка труда мидл-разработчика, а не измеренное время агента.

D1/D2 подтверждены: фиксированная сумма, последующий возврат, независимые
транзакции, новые финансовые ссылки/курсы и защита удаления модуля. Серверный
набор: 102 теста, 101 прошёл, 1 пропущен без `mrp`. Проверены повторное обновление
и сохранность истории. Замеры: 1000 POS-строк — просмотр 3,23 с / применение
4,59 с; 10 000 исторических движений — просмотр 3,80 с. Подробности и границы
проверки приведены в [discovery.md](discovery.md).

Фактические часы мидл-разработчика и часы на единицу не измерены. Отдельная
чистая установка, браузерная проверка и рабочее применение не выполнялись.
