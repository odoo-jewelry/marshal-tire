# Оценка реализации

## Итог

- Всего сценариев: 22
- Implementation-driving сценариев: 14
- Verification-only сценариев: 8
- Implementation clusters: 4
- Implementation units: 9
- Fast path: нет
- Эмпирический размер: medium
- Производительность: 1 час на unit
- Базовая оценка: 9 часов
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 8–11 часов
- Уверенность: средне-высокая

Оценка относится к активному времени мидл Odoo-разработчика и включает focused tests, static checks, module update и обычный non-browser smoke.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| purchase-price-control | Configure price control for one company | implementation-driving | C1 | security | Нужны company settings и settings bridge |
| purchase-price-control | Reject a non-positive rounding step | implementation-driving | C1 | — | Нужна серверная валидация |
| purchase-price-control | Different reference prices by company | implementation-driving | C1 | security | Нужна company-dependent цена варианта |
| purchase-price-control | Inventory valuation remains unchanged | verification-only | C1 | stock, accounting | Проверяет изоляцию нового поля от valuation |
| purchase-price-control | Display markup based on a saved reference price | implementation-driving | C2 | — | Нужен расчёт markup |
| purchase-price-control | Use the default markup without a reference price | implementation-driving | C2 | — | Нужна fallback-ветка |
| purchase-price-control | Ignore non-product lines | implementation-driving | C2 | — | Нужна фильтрация eligible lines |
| purchase-price-control | Apply discount and taxes | implementation-driving | C2 | accounting | Нужен стандартный tax engine для unit value |
| purchase-price-control | Convert purchase unit and currency | implementation-driving | C2 | accounting | Нужна координация UoM и currency helpers |
| purchase-price-control | Recalculate after commercial terms change | implementation-driving | C2 | — | Нужны полные compute dependencies |
| purchase-price-control | Round upward to a whole-price step | implementation-driving | C2 | — | Нужен ceiling helper |
| purchase-price-control | Preserve an exact multiple | verification-only | C2 | uncertainty | Проверка floating boundary того же helper |
| purchase-price-control | Round upward to a fractional step | verification-only | C2 | uncertainty | Проверка fractional шага того же helper |
| purchase-price-control | Save an explicitly selected line | implementation-driving | C4 | procurement | Нужен confirm hook и ordered payload |
| purchase-price-control | Do not save an unselected line | verification-only | C4 | procurement | Regression стандартного confirm |
| purchase-price-control | Confirmation enters approval workflow | implementation-driving | C4 | procurement | Нужна фиксация на Confirm, не Approve |
| purchase-price-control | Multiple selected lines target the same sales-price owner | implementation-driving | C4 | bulk | Нужен детерминированный порядок |
| purchase-price-control | Failed confirmation is atomic | verification-only | C4 | procurement | Проверяет стандартную транзакционность механизма |
| purchase-price-control | Cancel a confirmed order | verification-only | C4 | procurement | Проверяет отсутствие custom rollback |
| purchase-price-control | Copy a purchase order | implementation-driving | C4 | — | Нужна copy semantics флажка |
| purchase-price-control | Confirm again after resetting to draft | verification-only | C4 | procurement | Проверяет повторный lifecycle того же hook |
| purchase-price-control | User cannot update the product | verification-only | C4 | security | Проверяет отсутствие sudo и атомарный AccessError |

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Company-dependent product price, company settings, settings bridge и constraint | Configuration, validation, multi-company reference price, valuation isolation | 2 | Несколько простых расширений связанных стандартных моделей с multi-company проверкой |
| C2 | Batch-aware вычисления строки PO через tax, UoM, currency и rounding helpers | Markup, fallback, eligibility, tax/discount, conversion, dependencies, rounding | 3 | Нетривиальная согласованная ценовая логика с несколькими стандартными подсистемами |
| C3 | Наследование формы PO и Purchase settings | Наблюдаемость всех полей и редактирование настроек | 1 | Два узких view extension по известным точкам |
| C4 | Ordered server-side payload вокруг стандартного `button_confirm` | Saving, approval, ordering, copy, retry, cancellation, access, atomicity | 3 | Lifecycle hook с несколькими записями и focused regression testing |

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет.

### Дублирующиеся или пересекающиеся сценарии

- Сценарии округления намеренно разделены по boundary cases и покрываются одним механизмом.

### Недостающие сценарии

- Нет; happy path, validation, multi-company, permissions, cancellation, retry, approval, copy и unchanged behavior покрыты.

### Недостаточно определённые или противоречивые сценарии

- Нет. Принято, что standard `list_price` остаётся общей для компаний, а конфликтующие строки применяются последовательно.

## Расчёт трудозатрат

- Сумма implementation units: 9
- Hours per unit: 1
- Базовые часы: 9
- Discovery: 0 — стандартные extension points уже проверены
- Миграция или обработка данных: 0
- Production-like bulk/external coordination/special hardware: 0
- Необычная длительная или ручная проверка: 0
- Другие исключительные конкретные работы: 0
- Итоговый диапазон: 8–11 часов

## Стратегия проверки

### Автоматизированные тесты

- Требуются.
- Обоснование: изменение содержит tax/currency/UoM расчёты, multi-company property и purchase lifecycle.
- Минимальный набор: вычисления и rounding boundaries; выбранные/невыбранные строки; double approval; последовательные конфликты; copy/cancel/reconfirm; права; company isolation; неизменность valuation cost.

### Module update и smoke verification

- Python syntax/import checks, XML parsing и проверка inheritance targets.
- Обновление `purchase_price_control` на явной development DB и focused test suite.
- Ручная non-browser проверка колонок PO и секции Price Control; browser automation не выполняется.

## Основные факторы сложности

- Корректная tax-included unit price при любых типах purchase tax.
- Одновременная нормализация валюты и UoM.
- Ceiling без перескока точного кратного из-за float.
- Момент сохранения в double-validation lifecycle и общий owner продажной цены вариантов.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| stock | Нельзя изменить valuation cost | Отдельное поле и проверки Standard/AVCO/FIFO |
| accounting | Налоги и валюты могут дать неверную reference price | Стандартные tax/currency helpers и focused cases |
| procurement | Confirm/approval/reconfirm могут применить цену не в тот момент | Снимок состояния до `super`, lifecycle tests |
| security | Confirm может завершиться AccessError при записи продукта | Без `sudo`, atomicity test и явное требование прав |
| bulk | Несколько строк имеют общего owner цены | Детерминированный ordered payload и regression test |
| uncertainty | Floating ceiling на дробном шаге | Odoo helper и boundary tests |
| view-conflict | Другие addons могут менять список PO | Узкие XPath по стабильным field/name targets |

## Предположения

- `last_purchase_price` принадлежит варианту и компании.
- Эффективная цена включает налоги и скидку и хранится в валюте компании на базовую UoM.
- Наценка по умолчанию применяется только при `last_purchase_price <= 0`.
- Плановая цена readonly и всегда пересчитывается серверно.
- Стандартная глобальная семантика `list_price` принимается.

## Исключено из оценки

- История цен, pricelists, supplierinfo и vendor bills.
- Изменение valuation/accounting данных и миграция существующих цен.
- Browser automation и production deployment.

## Требуется discovery

- Нет.
- Обоснование: модели, view targets, confirm lifecycle и valuation semantics Odoo 19 исследованы.

## Условия пересмотра оценки

- Требование company-dependent продажной цены или ведения истории.
- Ручное редактирование рассчитанной цены с дополнительными правилами согласования.
- Сохранение по vendor bill/receipt вместо Confirm PO.
- Особые fiscal-position, cash-basis или compound-tax правила сверх стандартного tax engine.

## Фактический результат

Заполняется после реализации:

- Фактические часы:
- Отклонение от оценки:
- Причина отклонения:
- Фактические часы на unit:
- Изменения для будущей калибровки:
