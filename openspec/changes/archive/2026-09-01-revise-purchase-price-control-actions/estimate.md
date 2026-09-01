# Оценка реализации

## Итог

- Всего сценариев: 24
- Implementation-driving сценариев: 11
- Verification-only сценариев: 13
- Implementation clusters: 3
- Implementation units: 6
- Fast path: нет
- Эмпирический размер: medium
- Производительность: 1 час на implementation unit
- Базовая оценка: 6 часов
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 5–8 часов
- Уверенность: средне-высокая

Итоговая оценка — реалистичное активное рабочее время мидл Odoo-разработчика от начала реализации до готового и обычно проверенного изменения. Focused tests, static checks, один module update и обычный non-browser smoke включены в clusters.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| purchase-price-control | Fill snapshots for an order | implementation-driving | C1 | migration | Нужны stored snapshot fields и batch fill action |
| purchase-price-control | Derive markup from filled prices | verification-only | C1 | — | Проверяет существующую формулу при новом моменте фиксации |
| purchase-price-control | Use default markup while filling without a reference price | verification-only | C1 | — | Проверяет существующий fallback в общем fill mechanism |
| purchase-price-control | Fill from the order company | verification-only | C1 | security | Проверяет company context того же действия |
| purchase-price-control | Keep a snapshot stable | implementation-driving | C1 | migration | Требует убрать product dependencies из current-полей и хранить значения |
| purchase-price-control | Refresh an existing snapshot | verification-only | C1 | — | Повторный вызов использует тот же fill/write mechanism |
| purchase-price-control | Show the line action for a discrepancy | implementation-driving | C1, C3 | view-conflict | Нужны precision-aware flag и его отображение |
| purchase-price-control | Update both product prices from one line | implementation-driving | C2 | security | Нужна явная product write и последующий snapshot refresh |
| purchase-price-control | Hide the line action without a usable discrepancy | verification-only | C1, C3 | — | Проверяет границы общего eligibility/discrepancy flag |
| purchase-price-control | Update all differing lines | implementation-driving | C2 | bulk | Нужны order-level candidate selection и пакет применения |
| purchase-price-control | Resolve shared price owners deterministically | implementation-driving | C2 | bulk | Нужны ordered payload и final refresh при общих owners |
| purchase-price-control | Roll back a failed bulk update | verification-only | C2 | bulk, security | Проверяет стандартную транзакционность без ручных commits |
| purchase-price-control | Display initialized price-control information in any state | implementation-driving | C3 | view-conflict | Нужно убрать state restrictions и добавить object-buttons |
| purchase-price-control | Ignore non-product lines | verification-only | C1, C2 | — | Существующий eligibility helper переиспользуется всеми действиями |
| purchase-price-control | Round upward to a whole-price step | verification-only | C1 | uncertainty | Существующий rounding helper сохраняется с новым stored markup |
| purchase-price-control | Preserve an exact multiple | verification-only | C1 | uncertainty | Boundary test того же helper |
| purchase-price-control | Round upward to a fractional step | verification-only | C1 | uncertainty | Fractional boundary test того же helper |
| purchase-price-control | Do not calculate from an absent snapshot | implementation-driving | C1 | migration | Нужен явный initialization flag и compute gating |
| purchase-price-control | Confirm an order without a price side effect | implementation-driving | C2 | procurement | Требуется удалить custom confirm hook и его payload |
| purchase-price-control | Complete double validation without a price side effect | verification-only | C2 | procurement | Проверяет отсутствие регрессии стандартного lifecycle после удаления hook |
| purchase-price-control | Update prices from a non-draft order | implementation-driving | C2, C3 | security, view-conflict | Actions и UI не должны фильтровать state/locked |
| purchase-price-control | Copy a purchase order | implementation-driving | C1 | migration | Нужны `copy=False` и явное uninitialized состояние копии |
| purchase-price-control | User cannot fill an affected line | verification-only | C1 | security | Проверяет ORM permissions и atomicity без `sudo()` |
| purchase-price-control | User cannot update an affected product | verification-only | C2 | security, bulk | Проверяет права продукта и rollback обоих update paths |

Классификация:

- `implementation-driving` — требует нового или изменённого production-поведения;
- `verification-only` — покрывается тем же механизмом либо проверяет стандартную транзакционность, сохранённый прежний расчёт или отсутствие lifecycle-регрессии.

Каждый из 24 Scenario присутствует ровно один раз.

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Stored snapshot semantics на `purchase.order.line`, fill action, initialized/discrepancy flags и refactor planned calculation | Fill/refill, markup, company, persistence, eligibility, absent snapshot, rounding, copy, line rights | 2 | Связное расширение одной модели и известной вычислительной логики; tax/UoM/currency/rounding уже реализованы |
| C2 | Явные line/bulk product updates, ordered payload, final snapshot refresh и удаление confirm hook | Одиночная/массовая запись, shared owners, rollback, lifecycle independence, права | 3 | Нетривиальная координация строк и продуктов с bulk ordering, security и atomicity |
| C3 | Узкое наследование формы PO: header actions, строковая action-button и state-independent visibility | Доступность действий и отображение во всех состояниях | 1 | Один известный view extension, но readonly one2many требует focused smoke |

Сумма: `2 + 3 + 1 = 6` implementation units.

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет. Права на заполнение строки и запись продукта уже разделены.

### Дублирующиеся или пересекающиеся сценарии

- Три rounding-сценария намеренно проверяют разные boundary cases одного helper.
- Display-state и non-draft update пересекаются по состояниям, но отдельно проверяют наблюдаемость UI и серверную запись.

### Недостающие сценарии

- Нет: заполнение, повторное заполнение, сохранённость снимка, line/bulk actions, конфликтующие owners, lifecycle, copy, permissions, multi-company и unchanged confirmation покрыты.

### Недостаточно определённые или противоречивые сценарии

- Историческое имя modified requirement `Explicit price saving on confirmation` сохранено для корректного delta-сопоставления; новое требование однозначно запрещает confirm-driven запись.
- Под «активной кнопкой» принято наличие доступного action при initialized monetary discrepancy; без снимка действие недоступно.

## Расчёт трудозатрат

- Сумма implementation units: 6
- Hours per unit: 1
- Базовые часы: 6
- Discovery: 0 — addon и standard Odoo 19 extension points исследованы
- Миграция или обработка данных: 0 — schema update стандартный, backfill намеренно отсутствует
- Production-like bulk/external coordination/special hardware: 0
- Необычная длительная или ручная проверка: 0
- Другие исключительные конкретные работы: 0
- Итоговый диапазон: 5–8 часов

Разброс учитывает проверку object-button в readonly one2many и конфликтов общего sales-price owner. Обычные тесты и module update повторно не добавляются.

## Стратегия проверки

### Автоматизированные тесты

- Требуются.
- Обоснование: меняются persisted semantics, product writes, bulk ordering, права, multi-company и отсутствие прежнего Purchase lifecycle side effect.
- Минимальный набор: snapshot fill/refill/stability; initialization gating; calculation/rounding regressions; line action; Update All; shared owner; all-state behavior; copy; permissions/rollback; company isolation; confirm/double approval без side effects; неизменность valuation.

### Module update и smoke verification

- Python syntax/imports, XML parse и проверка external IDs/XPath.
- Обновление `purchase_price_control` на явной development DB и focused backend suite.
- Проверка создания stored columns без backfill и игнорирования старого `save_prices`.
- Ручной non-browser smoke обеих header-кнопок и строковой кнопки в draft, confirmed, locked и cancelled PO. Browser automation не запускается.

## Основные факторы сложности

- Refactor одних и тех же `current_*` полей из dynamic compute в устойчивый stored snapshot.
- Денежное сравнение с currency precision и отдельным configured rounding step.
- Согласованный refresh снимков после shared product/template writes.
- Доступность object-buttons внутри readonly embedded list.
- Атомарность нескольких product и PO-line writes без повышения прав.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| migration | Существующие строки получают пустой снимок, а старые флажки перестают действовать | Явный initialization flag, module update test, без недостоверного backfill |
| bulk | Несколько строк могут писать один product/template owner | Ordered payload, final refresh и focused conflict tests |
| security | Закрытая строка или продукт могут быть недоступны для записи | Без `sudo()`, representative users и rollback tests |
| procurement | Удаляется прежний confirm hook | Regression tests confirm, approval, cancel и reconfirm |
| uncertainty | Float/currency precision может неверно показать discrepancy | `float_compare` и boundary tests |
| view-conflict | Readonly one2many или другие addons могут влиять на кнопки | Узкий XPath, module update и ручной all-state smoke |

## Предположения

- Fill полностью перезаписывает снимок всех eligible строк заказа и не меняет продукты.
- До Fill планируемая цена не используется для update, даже если effective price положительна.
- После успешного Update refresh затрагивает связанные строки текущего заказа, а не все PO базы.
- Product writes выполняются в порядке `(order, sequence, id)`; последняя строка выигрывает.
- `last_purchase_price` company-dependent, `lst_price` сохраняет стандартную глобальную семантику.
- Действия разрешены во всех состояниях, но не обходят ACL и record rules.

## Исключено из оценки

- История цен, новый wizard/model, pricelists, supplierinfo и vendor bills.
- Company-dependent продажная цена и автоматическое разрешение конфликтов.
- Изменение valuation/accounting данных или удаление старого DB-столбца.
- Browser automation, production deployment и массовый backfill существующих PO.

## Требуется discovery

- Нет.
- Обоснование: текущий addon, поля продукта, standard Purchase form и lifecycle Odoo 19 уже исследованы. UI-риск проверяется обычным smoke в рамках реализации.

## Условия пересмотра оценки

- Потребуется сохранять историю снимков или автоматически backfill существующих заказов.
- Кнопки должны обходить стандартные права либо потребуют новой security group.
- Продажная цена станет company-dependent или будет записываться в pricelist.
- Object-button в readonly list потребует существенного OWL-компонента вместо узкого view extension.
- Update All должен поддерживать интерактивное разрешение конфликтов или частичный success.

## Фактический результат

Заполняется после реализации:

- Фактические часы:
- Отклонение от оценки:
- Причина отклонения:
- Фактические часы на unit:
- Изменения для будущей калибровки:
