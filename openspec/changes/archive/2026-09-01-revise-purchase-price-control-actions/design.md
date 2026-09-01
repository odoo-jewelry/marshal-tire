## Context

`main/purchase_price_control` уже расширяет `purchase.order.line` non-stored полями `current_purchase_price`, `current_sale_price`, `current_markup`, `effective_purchase_price`, `planned_sale_price` и stored-флажком `save_prices`. Текущие значения динамически читаются из продукта, а `purchase.order.button_confirm()` после стандартного подтверждения записывает цены отмеченных строк.

В стандартном Odoo 19 форма `purchase.purchase_order_form` содержит header и editable `order_line`; после подтверждения или блокировки сам список становится readonly, но `type="object"` действия могут быть отдельно доступны. Стандартный `purchase.order.button_confirm()` отвечает только за Purchase lifecycle и не должен больше быть extension point ценовой записи.

Справочная закупочная цена остаётся company-dependent значением варианта продукта, а стандартная `lst_price` через inverse принадлежит шаблону и не является company-dependent. Эффективная цена строки по-прежнему вычисляется стандартными tax, UoM и currency helpers. Изменение вводит намеренный хранимый снимок на строке PO; это не аудит истории продукта, а зафиксированная пользователем база для сравнения и наценки.

## Goals / Non-Goals

**Goals:**

- заменить `save_prices` и confirm-driven запись явными действиями строки и заказа;
- хранить загруженные пользователем текущие закупочную и продажную цены и рассчитанную наценку в строке;
- разрешить заполнение и запись цен во всех состояниях PO, включая confirmed, locked и cancelled;
- показывать действие строки только при инициализированном снимке и реальном денежном расхождении;
- сохранить текущие правила effective price, markup fallback, rounding, multi-company, прав и атомарности;
- обеспечить безопасное обновление существующей базы без реконструкции исторических снимков.

**Non-Goals:**

- изменение `standard_price`, valuation, supplierinfo, pricelists или бухгалтерских данных;
- автоматическая запись цен при любом Purchase lifecycle event;
- полноценная история или аудит цен;
- устранение стандартной глобальной семантики `list_price` и конфликтов вариантов;
- отдельный wizard подтверждения или новый persistent model.

## Decisions

### 1. Затрагиваемые компоненты

Изменяется только addon `main/purchase_price_control`:

- `models/purchase_order_line.py`: stored-снимок, вычисляемое расхождение и действие строки;
- `models/purchase_order.py`: массовое заполнение, массовое обновление и агрегированный признак доступности;
- `views/purchase_order_views.xml`: две header-кнопки и кнопка строки вместо `save_prices`;
- `tests/test_purchase_price_control.py`: замена confirm-driven сценариев на action-driven и snapshot-сценарии;
- `i18n/purchase_price_control.pot`, `i18n/ru.po`, `i18n/uk.po`: новые action labels и удаление пользовательского текста флажка;
- `__manifest__.py`: version bump; зависимости и data order не меняются.

`product_product.py`, company settings и settings view функционально не меняются. Новые модели, ACL, record rules и data XML не нужны: используются существующие записи и их стандартные права.

### 2. Источники истины и поля строки

| Значение | Владелец | Семантика |
|---|---|---|
| Фактическая справочная закупочная цена | `product.product.last_purchase_price` | company-dependent, валюта компании / базовая UoM |
| Фактическая продажная цена | `product.product.lst_price` | стандартная общая цена варианта/шаблона |
| `current_purchase_price` | `purchase.order.line` | stored snapshot фактической закупочной цены на момент Fill/refresh |
| `current_sale_price` | `purchase.order.line` | stored snapshot фактической продажной цены на момент Fill/refresh |
| `current_markup` | `purchase.order.line` | stored snapshot процента наценки, рассчитанного при Fill/refresh |
| `price_snapshot_initialized` | `purchase.order.line` | stored Boolean, отличает незаполненную строку от корректного нулевого снимка |
| `effective_purchase_price` | `purchase.order.line` | прежнее non-stored вычисление из условий PO |
| `planned_sale_price` | `purchase.order.line` | non-stored вычисление из effective price и stored markup только при initialized snapshot |
| `price_update_required` | `purchase.order.line` | non-stored Boolean доступности действия строки |

Три `current_*` поля перестают зависеть от продукта и становятся readonly в UI, stored и `copy=False`. `price_snapshot_initialized` также имеет `copy=False`. Поэтому новые, скопированные и существующие после upgrade строки имеют явное uninitialized-состояние; историческое значение не угадывается.

`planned_sale_price` сохраняет текущую формулу и ceiling rounding, но использует stored `current_markup`. До заполнения снимка он возвращает `0.0`, а `price_update_required=False`. Изменение коммерческих условий PO пересчитывает effective/planned значения, но не меняет снимок.

`price_update_required` сравнивает пары `current_purchase_price`/`effective_purchase_price` и `current_sale_price`/`planned_sale_price` через `float_compare(..., precision_rounding=company.currency_id.rounding)`. Он истинен только для eligible и initialized строки. На `purchase.order` non-stored `has_price_updates` агрегирует этот признак для UI `Update All`; отдельный `has_price_control_lines` может управлять доступностью Fill без привязки к state.

### 3. Заполнение снимков

Публичное batch-aware действие `purchase.order.action_fill_current_prices()` обрабатывает eligible строки выбранных заказов независимо от `state` и `locked`:

1. Для каждой строки читает продукт через `with_company(order.company_id)`.
2. Сохраняет в строке `last_purchase_price` и `lst_price` продукта.
3. Рассчитывает markup как `(sale / purchase - 1) * 100`, если purchase больше нуля; иначе использует `company.purchase_default_markup`.
4. Устанавливает `price_snapshot_initialized=True`; dependent planned price и discrepancy пересчитываются ORM.

Действие не записывает продукт и всегда заменяет прежний снимок. Display, section, subsection, note и down-payment строки игнорируются. Запись выполняется обычным ORM без `sudo()`; ошибка одной строки откатывает всё действие.

### 4. Одиночное обновление

`purchase.order.line.action_update_product_prices()` является серверным действием строки и повторно проверяет eligibility, initialization и discrepancy, не доверяя только UI. Для уже совпадающей или неподходящей строки действие является безопасным no-op, что обеспечивает retry/API идемпотентность.

Для подходящей строки сервер заново получает computed effective/planned значения и одной логической операцией записывает:

- `effective_purchase_price` в `product_id.with_company(order.company_id).last_purchase_price`;
- `planned_sale_price` через стандартный inverse `product_id.lst_price`.

После успешной записи обновляются снимки всех eligible строк того же заказа, чьи продукты или общий sales-price owner затронуты. Снимки читаются из итоговых product values, поэтому нажатая кнопка исчезает, а возможное расхождение другой строки того же продукта/шаблона становится видимым. Не используются `sudo()`, ручной commit или обход стандартного inverse.

### 5. Массовое обновление

`purchase.order.action_update_all_prices()` повторно фильтрует eligible, initialized и differing строки серверно и сортирует их по `(order, sequence, id)`. Calculated payload фиксируется до первой product write, чтобы применение одной строки не меняло markup/planned payload следующей.

Payload применяется последовательно. При нескольких строках одного продукта последняя строка определяет final `last_purchase_price`; при вариантах общего шаблона последняя строка определяет final shared sales price. После всех записей снимки затронутых eligible строк обновляются из итоговых product values. Это сохраняет детерминированность и показывает оставшиеся расхождения вместо их скрытия.

Пустой candidate set является безопасным no-op. Любая AccessError, validation error или product inverse error откатывает все product writes и snapshot refresh в общей транзакции.

### 6. UI и lifecycle

В header формы PO узким наследованием добавляются `Fill Current Prices` и `Update All` как `type="object"`. Они не имеют state/locked restrictions; `Update All` скрыт или недоступен без `has_price_updates`, а Fill доступен при наличии eligible строк.

В embedded list после planned price размещается строковая `Update` object-button с `invisible="not price_update_required"`. `save_prices` удаляется из модели и view. Информационные колонки остаются readonly и доступны во всех состояниях заказа; readonly стандартного `order_line` не должен скрывать custom object-button.

Override `purchase.order.button_confirm()` удаляется полностью. Confirm, double approval, cancel, reset to draft, lock/unlock и повторное подтверждение не заполняют снимки, не записывают и не откатывают цены. Явные действия работают и после этих переходов. API/RPC получает ту же семантику при вызове action methods; прямой import не запускает скрытое сохранение продуктов.

При duplicate поля снимка и initialization очищаются благодаря `copy=False`. Пользователь явно запускает Fill в копии.

### 7. Права и multi-company

Все чтения и записи справочной закупочной цены используют `order.company_id` и `with_company`; ambient company не является источником выбора. `lst_price` остаётся стандартно глобальной для шаблона, поэтому update из одной компании виден другим компаниям.

Действия выполняются от текущего пользователя без `sudo()`. Fill требует возможности записать строки PO; Update дополнительно требует стандартного права записи затронутых продуктов. Если строка confirmed/locked/cancelled доступна только для чтения из-за record rule, action завершается AccessError и ничего частично не сохраняет. Новые права не выдаются.

### 8. Upgrade и данные

При module update Odoo создаёт stored columns для прежних non-stored `current_*` полей и новых technical flags. Они получают нулевые/default значения с `price_snapshot_initialized=False`. Автоматический backfill не выполняется: историческую точку снимка достоверно восстановить нельзя, а текущие product values пользователь может загрузить Fill-действием.

Поле `save_prices` удаляется из registry и UI. Его прежний столбец можно оставить в PostgreSQL как безвредный orphan; destructive drop migration не требуется. После upgrade ранее установленные флажки немедленно перестают влиять на Confirm, что является намеренной сменой требования. Product prices, existing PO lifecycle и valuation data при update не изменяются.

### 9. Проверка

Focused backend tests должны покрыть:

- uninitialized новые, существующие и copied строки;
- Fill для всех eligible строк, refill, default markup и устойчивость снимка к внешней смене product price;
- planned price dependencies, целые/дробные rounding boundaries и monetary comparison tolerance;
- visibility flags и server-side no-op для неподходящей/совпадающей строки;
- line Update в draft, confirmed, locked и cancelled состоянии;
- Update All, смешанный набор строк, deterministic ordering, общий product/template owner и refresh снимков;
- atomic rollback и права на строки/продукты без `sudo()`;
- company isolation `last_purchase_price` и глобальную семантику `lst_price`;
- отсутствие ценовых side effects у confirm/double approval/cancel/reset/reconfirm;
- неизменность `standard_price` и valuation для Standard, AVCO и FIFO;
- module update, Python/XML/static validation и переводы.

Browser tests не создаются и не запускаются по правилам проекта. Фактическую кликабельность object-buttons внутри readonly embedded list и header во всех состояниях нужно проверить ручным smoke test после module update.

## Risks / Trade-offs

- **Незаполненные существующие строки.** После upgrade они намеренно не получают поддельный исторический снимок; до Fill обновление недоступно.
- **Действия на cancelled/locked документах.** Это осознанное требование, которое позволяет менять master data из исторического документа; стандартный PO lifecycle при этом не меняется.
- **Глобальная продажная цена.** `lst_price` остаётся общей для шаблона, а reference purchase price — company-dependent. После refresh это может создать разные наблюдаемые расхождения между компаниями.
- **Конфликтующие строки.** Последняя строка выигрывает, а предыдущая может снова показать Update после final refresh. Это честно отражает невозможность одновременно сохранить разные цены одному owner.
- **Снимок не является аудитом.** Refill и успешный Update перезаписывают его; отдельная история не ведётся.
- **Права строки.** Fill/refresh требует записи PO line даже в закрытом состоянии; record rules могут законно блокировать действие.
- **UI readonly.** Нужно проверить, что Odoo 19 не подавляет embedded object-button в readonly one2many; если подавляет, допустим узкий статический frontend fallback без browser automation, но без расширения бизнес-семантики.

Отклонённые альтернативы:

- оставить current-поля dynamic — противоречит требованию явного фиксируемого снимка и делает Fill бессодержательным;
- продолжать обновление в `button_confirm()` — сохраняет нежелательную зависимость от lifecycle;
- хранить снимки в новой модели — избыточно без требования истории;
- использовать wizard для Update All — добавляет лишний шаг при уже явном действии;
- сравнивать Float через `!=` — нестабильно на валютных и rounding-границах;
- применять `sudo()` для закрытых PO — нарушает согласованную модель доступа;
- удалять старый столбец `save_prices` миграцией — необратимо и не требуется для поведения.
