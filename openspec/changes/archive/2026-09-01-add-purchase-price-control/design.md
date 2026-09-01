## Context

В Odoo 19 `purchase.order.line.price_unit` хранится в валюте PO и закупочной UoM, а налоги и скидка обрабатываются стандартным tax engine. `product.product.standard_price` является company-dependent учётной себестоимостью: при AVCO/FIFO она обновляется складской оценкой, а ручная запись способна затронуть оценочные записи. Поэтому она непригодна как источник справочной последней закупочной цены.

Продажная цена варианта доступна как `product.product.lst_price`; её inverse обновляет базовую `product.template.list_price` с учётом variant extra. `list_price` не является company-dependent. Пользователь осознанно принял последовательное применение строк, включая варианты одного шаблона: последняя строка определяет итоговую общую продажную цену.

В репозитории нет существующего addon с этой capability. Новый addon размещается в `main/purchase_price_control` и следует стандартной структуре Odoo 19. Основные extension points уже проверены: форма PO `purchase.purchase_order_form`, Purchase app в `base.res_config_settings_view_form` через стандартное purchase-наследование и `purchase.order.button_confirm()`.

## Goals / Non-Goals

**Goals:**

- отделить справочную последнюю закупочную цену от учётной себестоимости;
- показать и пересчитывать все показатели price control в строке PO;
- нормализовать цену с налогами и скидкой к валюте компании и базовой UoM;
- обновлять цены только по явному флажку при переходе из RFQ/RFQ Sent через Confirm;
- обеспечить воспроизводимое округление вверх, multi-company изоляцию и атомарность;
- сохранить стандартное подтверждение PO без изменений для неотмеченных строк.

**Non-Goals:**

- изменение `standard_price`, stock valuation layers, партийной оценки или бухгалтерских проводок;
- использование vendor bill как источника цены;
- изменение `product.supplierinfo`, customer pricelists или истории цен;
- автоматическое разрешение конфликтов нескольких строк/вариантов;
- откат цен при отмене PO;
- отдельная ручная форма редактирования `last_purchase_price` на карточке продукта в рамках первой версии.

## Decisions

### 1. Addon и зависимости

Создать addon `purchase_price_control` с зависимостями `purchase` и `stock_account`. `purchase` предоставляет PO, tax engine и продуктовые модели; `stock_account` фиксирует явную совместимость с учётной себестоимостью, которая должна оставаться неизменной, и позволяет тестировать Standard/AVCO/FIFO. Отдельные модели, ACL и record rules не требуются, поскольку расширяются существующие записи и используются их права.

Ожидаемые файлы:

- `__init__.py`, `__manifest__.py`;
- `models/__init__.py`;
- `models/product_product.py`;
- `models/res_company.py`;
- `models/res_config_settings.py`;
- `models/purchase_order_line.py`;
- `models/purchase_order.py`;
- `views/purchase_order_views.xml`;
- `views/res_config_settings_views.xml`;
- `tests/__init__.py`, `tests/test_purchase_price_control.py`.

### 2. Источники истины

| Значение | Владелец | Хранение | Валюта / UoM |
|---|---|---|---|
| Последняя закупочная цена | `product.product.last_purchase_price` | Float, `company_dependent=True` | валюта компании / базовая UoM продукта |
| Шаг округления | `res.company.purchase_price_rounding` | Float, default `0.01` | валюта компании |
| Наценка по умолчанию | `res.company.purchase_default_markup` | Float, default `0.0` | проценты |
| Текущая продажная цена | стандартный `product.product.lst_price` | стандартное поле/inverse | валюта продукта / базовая UoM |
| Цена строки PO | стандартные поля строки | `price_unit`, `discount`, `tax_ids` | валюта PO / закупочная UoM |

Настройки публикуются в `res.config.settings` как writable related-поля текущей компании. Constraint на `res.company` запрещает шаг `<= 0`; отрицательную наценку по умолчанию не запрещаем, чтобы не вводить неоговорённое бизнес-ограничение.

### 3. Поля и вычисления строки PO

На `purchase.order.line` добавить:

- `current_purchase_price`: computed, non-stored, readonly;
- `current_sale_price`: computed, non-stored, readonly;
- `current_markup`: computed, non-stored, readonly;
- `effective_purchase_price`: computed, non-stored, readonly;
- `planned_sale_price`: computed, non-stored, readonly;
- `save_prices`: Boolean, `copy=False`.

Non-stored поля показывают актуальные значения и не создают исторический snapshot. Для обычной продуктовой строки:

1. Сформировать стандартную tax base line для количества `1`, текущих `price_unit`, `discount`, `tax_ids`, партнёра, валюты и компании.
2. Стандартным `account.tax` engine получить tax-included total одного закупочного UoM. Это корректно обрабатывает price-included и price-excluded налоги без ручного сложения процентов.
3. Пересчитать цену из `product_uom_id` в базовую `product_id.uom_id` стандартным UoM helper.
4. Конвертировать из валюты PO в валюту компании стандартным currency helper на `date_order`; если даты нет — использовать context date по стандартному fallback.
5. Вычислить наценку:
   - если `last_purchase_price > 0`: `(lst_price / last_purchase_price - 1) * 100`;
   - иначе: `company.purchase_default_markup`.
6. Вычислить `raw_sale_price = effective_purchase_price * (1 + markup / 100)`.
7. Для положительного результата применить ceiling к кратному `purchase_price_rounding`. Реализация должна учитывать floating precision (`float_round(..., rounding_method='UP')` либо эквивалент с Odoo Decimal-safe helper), чтобы точное кратное не перескочило на следующий шаг.

Все вычисления должны работать серверно и batch-aware. `@api.depends`/`@api.depends_context('company')` должны включать продуктовые цены, коммерческие поля строки, валюту, дату, компанию, UoM и настройки. Для display/non-product/down-payment строк значения обнуляются и `save_prices` не применяется.

### 4. Представление

Узким наследованием формы PO добавить шесть колонок рядом с `price_unit`, `discount` и налогами. Информационные поля readonly; `save_prices` доступен только для обычной строки в `draft`/`sent`. Колонки могут быть optional, чтобы не перегрузить стандартный список, но ключевые planned/effective price и флажок должны быть доступны без открытия отдельной формы.

В Purchase settings добавить отдельный `block` с title `Price Control`, содержащий `purchase_default_markup` и `purchase_price_rounding`, с `company_dependent="1"`, пояснениями единиц и примерами шага `10`, `5`, `0.10`. Использовать стабильные `name`/`id`, а не XPath по переведённым строкам.

### 5. Подтверждение и порядок записи

Расширение `purchase.order.button_confirm()` должно:

1. определить только заказы, которые до вызова `super()` находятся в `draft`/`sent`;
2. для отмеченных eligible-строк пересчитать значения серверно и подготовить ordered payload;
3. вызвать `super().button_confirm()`;
4. только после успешного стандартного подтверждения применить payload в порядке `(order, sequence, id)`;
5. для каждой строки записать `last_purchase_price` в `product_id.with_company(order.company_id)` и planned price через стандартный inverse `product_id.lst_price`, без `sudo()`.

В одной транзакции ошибка standard confirm или product write откатывает весь confirm и все price updates. Запись после `super()` не влияет на вычисление последующих payload: все значения фиксируются до первого обновления, но применяются последовательно; последняя строка определяет итоговое общее поле продажной цены. Это соответствует решению пользователя «применяем по очереди» и исключает зависимость расчёта второй строки от уже изменённой первой.

При double validation цены сохраняются при нажатии Confirm и переходе в `to approve`, а не при `button_approve`. Повторный вызов `button_confirm` для уже активного заказа ничего не применяет. После явного reset to draft новое подтверждение считается новым событием и снова пересчитывает значения. Отмена не откатывает продуктовые цены. `copy=False` очищает флажок в копиях PO и строк, созданных стандартным duplicate; импорт/API могут явно передать флажок и получают ту же серверную семантику подтверждения.

### 6. Права и multi-company

Настройки доступны в стандартной Purchase settings area группе Purchase Manager/System согласно родительскому view. Расчёты используют `order.company_id`, а не ambient company. `last_purchase_price` читается и пишется через `with_company(order.company_id)`, сохраняя company-dependent изоляцию.

Не использовать `sudo()`: подтверждающий пользователь должен иметь право записи продукта. При AccessError вся транзакция откатывается. Это предотвращает скрытое повышение полномочий. Стандартная `list_price` глобальна для шаблона и потому изменение продажной цены наблюдаемо во всех компаниях; это ограничение явно принимается в первой версии. Company-dependent продажная цена потребовала бы отдельной модели/прайс-листа и меняла бы scope.

### 7. Миграция и upgrade safety

Существующие записи не преобразуются. Новое company-dependent поле при отсутствии property читается как `0.0`; новые company settings получают defaults. Версионная migration не нужна. Manifest должен загружать settings view после PO view в детерминированном порядке. Установка и обновление addon не должны менять существующие PO или цены продуктов.

### 8. Проверка

Focused `TransactionCase`/purchase common tests должны покрыть:

- markup от сохранённой цены и fallback на default;
- налоги, скидку, purchase UoM, валюту и дату курса;
- ceiling для `10`, точного кратного и `0.10`;
- выбранную и невыбранную строки, non-product/down-payment;
- double validation, cancel, copy, reset/reconfirm и атомарность ошибки;
- последовательные строки одного продукта и варианты общего template;
- company-dependent `last_purchase_price` и settings;
- неизменность `standard_price`/valuation для Standard, AVCO и FIFO;
- поведение прав без `sudo()`;
- module install/update, Python/XML/static checks.

Browser-based тесты не создаются и не запускаются согласно правилам проекта; UI проверяется компиляцией view и ручным smoke test при реализации.

## Risks / Trade-offs

- **Продажная цена не company-dependent.** Изменение из PO одной компании обновляет общий `list_price`. Принято как стандартная семантика Odoo; альтернативой был бы отдельный pricelist, что выходит за scope.
- **Tax-included reference price отличается от обычной закупочной себестоимости.** Это прямое бизнес-требование; поле названо reference/last purchase price и не используется в valuation.
- **Последовательные варианты конфликтуют через template price.** Последняя строка выигрывает; UI не блокирует и не предупреждает согласно явному решению пользователя.
- **Non-stored показатели не являются аудитом.** После подтверждения они отражают уже обновлённые текущие цены. История цен намеренно исключена.
- **Права продукта могут остановить подтверждение.** Это безопаснее `sudo()`; организационно пользователям, которым разрешён Save Prices, нужны стандартные права изменения продукта.
- **Floating-point границы при ceiling.** Использование стандартного Odoo rounding helper и тесты точных кратных обязательны.

Отклонённые альтернативы:

- `standard_price` — отклонено из-за связи с AVCO/FIFO и valuation;
- `product.supplierinfo` — цена привязана к поставщику, валюте, количеству и UoM и не является единым company reference;
- vendor bill price — отсутствует на момент Confirm и не соответствует выбранному источнику;
- stored snapshots на PO line — добавляют историю и migration semantics без требования;
- onchange-only логика — не покрывает import/API и небезопасна для бизнес-инварианта;
- сохранение до `super().button_confirm()` — создаёт менее ясную зависимость от успешности стандартного lifecycle, хотя транзакция формально атомарна.
