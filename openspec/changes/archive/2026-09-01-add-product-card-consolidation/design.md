## Context

В Odoo 19 CE `product.product` делегирует общие поля в `product.template`; удаление последнего варианта также удаляет шаблон. Большинство операционных таблиц ссылается на вариант, а конфигурация может ссылаться как на вариант, так и на шаблон. Связи со складом и документами используют разные `ondelete`, состояния и бизнес-ограничения, поэтому универсальное переназначение внешних ключей не является допустимым extension point.

В проекте сейчас 272 активных шаблона и варианта, все шаблоны одновариантные. Установлены Product, Purchase, Sales, Inventory, Accounting и Point of Sale; `purchase_import` ищет варианты напрямую по `default_code`, `barcode` и supplierinfo. Стандартный Odoo предоставляет архивирование товара и специализированный merge контактов, но не merge товаров. `data_recycle` также не переносит товарные ссылки.

Capability будет реализована отдельным addon `product_card_consolidation` в `main/`. Это отделяет общее управление каталогом от отраслевого addon `tire`, но addon будет зависеть от `purchase_import`, чтобы поддержка альтернативных идентификаторов была частью одной устанавливаемой и тестируемой возможности.

## Goals / Non-Goals

**Goals:**

- дать авторизованному менеджеру каталога безопасный wizard с preview и явным выбором canonical/duplicate;
- сохранить confirmed, done, cancelled и posted историю без изменения `product_id`;
- перенести явно разрешённые справочные связи и editable draft references через ORM;
- архивировать duplicate и обеспечить поиск canonical по прежним `default_code`, `barcode` и supplier code;
- гарантировать серверные проверки, повторную проверку перед записью, атомарность и аудит;
- сохранить standard behavior, когда объединение и aliases не используются;
- обеспечить безопасную установку на существующую БД без начального преобразования данных.

**Non-Goals:**

- SQL/ORM-переназначение всех ссылок на товар;
- изменение проведённой бухгалтерии, POS history, confirmed procurement или done stock moves;
- перенос stock quants, reserved quantities, valuation layers или стоимости остатков;
- tracked products, lots/serials, multi-variant templates и variant mapping;
- слияние scalar values двух карточек или интерактивный выбор каждого поля;
- alias-сканирование в POS frontend;
- внешние ID `ir.model.data`, generic `Reference` fields и произвольные связи неизвестных addon;
- массовое обнаружение и автоматическое объединение групп дублей;
- автоматический rollback уже успешно выполненного объединения.

## Decisions

### 1. Новый addon и зависимости

Создаётся addon `main/product_card_consolidation` с зависимостями:

- `purchase_import` — уже приводит `purchase` и `stock` и предоставляет целевой import flow;
- `sale_management` — для draft quotation lines;
- `point_of_sale` не нужен как обязательная зависимость: стандартный active domain исключит архивный duplicate из нового POS-каталога, а POS history не меняется.

Предполагаемые файлы:

- `__manifest__.py`, `__init__.py`;
- `models/product_template.py`, `models/product_product.py`, `models/product_identifier_alias.py`;
- `wizard/product_card_consolidation.py` и view wizard;
- `views/product_template_views.xml` для canonical link/ribbon и bound server action;
- `security/product_card_consolidation_security.xml`, `security/ir.model.access.csv`;
- focused tests в `tests/test_product_card_consolidation.py` и import integration tests.

Серверное действие привязывается к списку `product.template`. Variant-list action не добавляется в первом scope: все проверки и пользовательское понятие «карточки» относятся к шаблону, а выбранный единственный вариант определяется сервером.

### 2. Источник истины и новые данные

На `product.template` добавляются:

- `merged_into_id`: readonly `Many2one` на canonical template, `copy=False`, indexed, с защитой от self-link/cycle;
- `merged_source_ids`: обратная readonly связь для просмотра ранее поглощённых карточек.

Canonical template является источником истины для name, descriptions, images, category, taxes, routes, prices, company-dependent `standard_price`, custom `last_purchase_price`, accounting properties и всех остальных scalar values. Эти значения не суммируются и не заменяются значениями duplicate.

Для нескольких прежних identifiers нужен отдельный persistent model `product.identifier.alias`; одного поля на standard product недостаточно. Он хранит:

- canonical `product_id`;
- optional `source_product_id` для аудита;
- `identifier_type` (`default_code` или `barcode`);
- исходное `value` и нормализованное indexed value;
- `company_id`, соответствующую exact company ownership canonical product.

Aliases принадлежат canonical variant. Уникальность нормализованного `(identifier_type, value, company scope)` проверяется серверно с учётом direct identifiers активных товаров; конфликт блокирует preview/confirmation. Пустые значения и значение, уже равное canonical identifier, alias не создают.

Supplier codes не дублируются в alias model. Их источником истины остаётся `product.supplierinfo`, который переносится или дедуплицируется по supplier/company/currency/UoM/minimum quantity и variant. Это сохраняет partner-specific semantics.

### 3. Wizard и preview

Transient wizard получает selected template IDs из context, требует ровно две active cards и отдельное поле canonical template. Строки preview также transient и содержат severity, category, count и безопасно сформированное сообщение. Preview не изменяет persistent данные.

Preview формируется одним серверным анализом:

1. определяет canonical и duplicate template/variant;
2. проверяет базовую совместимость;
3. считает draft references, preserved history и переносимую configuration;
4. выявляет identifier и configuration conflicts;
5. показывает scalar policy «canonical wins»;
6. сохраняет fingerprint значимых `write_date`/IDs только как UI hint.

Confirmation не доверяет fingerprint: она повторяет полный анализ по текущим данным. Кнопка Confirm доступна только при отсутствии blocker lines и открывает отдельный standard confirmation dialog/context action с недвусмысленным предупреждением об архивировании.

### 4. Eligibility policy

Обе карточки должны:

- существовать, быть active и не иметь `merged_into_id`;
- иметь ровно один variant с учётом archived variants;
- иметь одинаковый exact `company_id` (оба shared либо одна и та же company);
- находиться в `allowed_company_ids` пользователя;
- иметь одинаковые product type/storage semantics, `uom_id` и UoM category;
- иметь `tracking = none` и не иметь `stock.lot`;
- не иметь non-zero `stock.quant.quantity`, `reserved_quantity` или незавершённого inventory count.

Canonical, который ранее поглотил другие duplicates, разрешён. Archived/merged source нельзя выбрать снова. `action_unarchive` для template/variant с `merged_into_id` отклоняется серверно, поэтому duplicate не возвращается случайно в каталог.

В installation scope отсутствует stock valuation merge. Если позднее будет установлен или добавлен addon, создающий valuation records, они считаются preserved history; наличие нулевого текущего остатка остаётся обязательным.

### 5. Явная policy связанных данных

Никакого generic FK discovery/update не выполняется. В модели сервиса есть расширяемая декларация supported handlers, а неизвестные ссылки остаются неизменными и отображаются как preserved references. Это позволяет другим addon добавить собственный handler через inheritance.

Переносятся через ORM:

- `sale.order.line` только для quotation states `draft`/`sent`, если standard `product_updatable` разрешает изменение;
- `purchase.order.line` только в RFQ states `draft`/`sent`;
- `product.supplierinfo`, variant/template pricelist rules, routes, taxes, tags, optional-product relations, packaging, putaway rules, storage capacities и orderpoints по отдельным handlers;
- project references `purchase.import.profile.variant_template_id` только если они указывают на duplicate; transient import wizard/preview не считается durable configuration и может истечь стандартно.

Для relational configuration применяются правила:

- Many2many values объединяются как set union;
- полностью эквивалентные duplicate rules удаляются после привязки/сохранения canonical equivalent;
- natural-key collision с разными business values создаёт blocker и требует ручного исправления до нового preview;
- scalar fields canonical card никогда не перезаписываются.

Сохраняются без изменения:

- non-draft sale/purchase lines;
- все accounting and POS lines независимо от состояния;
- confirmed/cancelled/done stock moves and move lines;
- lots, returns, scraps и исторические generic references;
- source attachments/messages, чтобы архивная карточка оставалась полноценной точкой аудита.

Сначала выполняются все reference/configuration writes, затем создаются aliases и canonical link, после чего duplicate template архивируется через standard `action_archive()`. Canonical и duplicate перечитываются с `active_test=False` на каждом критическом шаге.

### 6. Backend search и purchase import

На `product.product` добавляется общий batch helper для exact resolution набора identifiers с company scope. Он возвращает direct active matches и alias matches, не скрывая ambiguity. `purchase_import` использует helper внутри существующего `_build_lookup_cache`, поэтому его текущие priority, ambiguity errors и read-only preview сохраняются.

Backend display-name search расширяется alias domain только для поддерживаемых положительных текстовых операторов. Direct standard search остаётся первой ветвью, domain/access rules/active filtering и limit сохраняются. Alias никогда не возвращает archived source.

POS browser dataset не расширяется aliases. После reload/archive source исчезнет из нового POS catalog стандартным способом; старый barcode не сканируется в POS, пока это не будет отдельно специфицировано.

### 7. Lifecycle, API, audit и транзакция

Business action находится на persistent product service/model, а wizard только собирает выбор и вызывает его. Поэтому UI, RPC и будущий API проходят одинаковые checks. Метод поддерживает ровно одну пару по контракту и явно валидирует права.

Операция выполняется в текущей транзакции без `commit()` и без подавления исключений. Любая ошибка откатывает draft references, configuration, aliases, link и archive вместе. Retry запускает новый полный preview/validation; успешный source повторно использовать нельзя.

После успеха canonical chatter получает одно сообщение с source link, пользователем, временем и summary перенесённых/preserved категорий. Duplicate получает readonly link на canonical; его существующий chatter не переносится. Cancellation wizard не выполняет writes.

### 8. Permissions и multi-company

Создаётся отдельная группа `product_card_consolidation.group_product_consolidation_manager` в product-management privilege. Она назначается ответственным администраторам явно и не выдаётся автоматически всем Inventory Managers. Только эта группа получает create/read/write/unlink на transient wizard и управляемый alias model. Поля aliases и `merged_into_id` не редактируются в обычных формах; CRUD-защита разрешает их изменение только consolidation service после повторной проверки группы.

Business action повторно проверяет группу, доступ к обеим карточкам и принадлежность их exact company к `allowed_company_ids`. После этих проверок service использует узко ограниченный `sudo()` только для заранее перечисленных draft/configuration recordsets: это необходимо, чтобы одна административная операция не зависела от случайной комбинации Sales/Purchase/Inventory ACL пользователя. `sudo()` не применяется к поиску произвольных records, не расширяет company scope и не меняет preserved history. Preview показывает агрегированные counts/conflicts без раскрытия закрытых документов.

Обе карточки должны иметь exact одинаковый `company_id`; shared и company-specific cards не объединяются. Company-dependent scalar values canonical сохраняются по всем компаниям и не читаются/переносятся из duplicate.

### 9. Migration и upgrade

Addon устанавливается с пустыми `merged_into_id` и alias table; существующие product/document records не обновляются. Data migration не требуется. Индексы и constraints создаются декларативно при установке.

При module upgrade новые handlers или alias semantics не должны автоматически консолидировать существующие карточки. Любой будущий backfill aliases потребует отдельной versioned migration и отдельного решения о конфликтной политике.

Удаление addon не должно удалять стандартные business records. Custom alias records и merge links могут быть удалены штатным uninstall, но archived products остаются archived; это известное необратимое operational consequence и будет отражено в предупреждении установки/документации.

### 10. Testing strategy

`TransactionCase`/`SavepointCase` tests должны покрыть:

- selection, canonical choice, preview categories и cancellation;
- multi-variant, company, type/UoM, tracking/lot, quant/reservation и stale-preview blockers;
- canonical scalar preservation, M2M union, exact dedup и conflicting rule blockers;
- draft sale/RFQ references и неизменность confirmed/done/cancelled/posted/POS history;
- duplicate archive/link, unarchive guard и repeated merge into an existing canonical;
- direct/alias ambiguity, backend lookup, `purchase_import` preview and apply by old code/barcode/supplier code;
- permissions through UI-equivalent methods and direct model API;
- forced mid-operation failure proving transaction rollback, then successful retry;
- shared/same/cross-company behavior and access-limited configuration;
- unchanged standard search, archive, import and ordinary product flows when no merge metadata exists.

Validation additionally includes manifest/data order, ACL/external IDs, XML compilation, module install/update and focused non-browser tests. Browser automation is excluded by repository policy; POS catalog removal and wizard rendering receive static/XML review plus manual smoke verification.

## Risks / Trade-offs

- **Исторические отчёты остаются разделёнными.** Это сознательная плата за неизменность stock/accounting history. Отдельное canonical reporting может быть последующим capability.
- **Архивный товар остаётся в открытых confirmed operations.** Это сохраняет traceability; завершение/возврат происходит на исходном товаре и не переводится на canonical.
- **Aliases усложняют поиск.** Exact direct identifier другого active product имеет приоритет конфликта, а не неявного выбора; ambiguity блокируется.
- **Allowlist требует сопровождения.** Новые addon со ссылками на products должны явно решить, являются ли их records draft configuration или immutable history.
- **Uninstall не является rollback.** Он удаляет механизм redirects, но не может безопасно автоматически разархивировать ранее объединённые products.
- **Отсутствует POS alias scan.** Старые штрихкоды поддерживаются backend/import, но не POS frontend в этом scope.

Отклонённые альтернативы:

- generic SQL/OpenUpgrade merge — обходит ORM lifecycle, меняет историю и плохо разрешает unique/business conflicts;
- перенос stock quants прямой заменой product — нарушает stock moves как источник истины;
- paired inventory adjustments — создают новые valuation/accounting effects и выходят за подтверждённый scope;
- удаление duplicate — разрушает ссылки истории или требует их ретроактивной замены;
- размещение в `tire` — делает общую catalog capability зависимой от отраслевого приложения;
- одно поле для old code/barcode — не поддерживает последовательное объединение нескольких duplicates;
- автоматический выбор scalar values — скрыто изменяет business master data и ухудшает auditability.
