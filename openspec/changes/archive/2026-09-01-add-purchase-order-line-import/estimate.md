# Оценка реализации

## Итог

- Всего сценариев: 39
- Implementation-driving сценариев: 21
- Verification-only сценариев: 18
- Implementation clusters: 9
- Implementation units: 32
- Fast path: нет
- Эмпирический размер: large
- Производительность: 1 час на unit (временная калибровка)
- Базовая оценка: 32 часа
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 32 часа для Odoo-разработчика middle-уровня
- Уверенность: средняя

Итоговая оценка включает focused investigation, production change,
обязательные focused tests, static checks, один module update и
обычную non-browser smoke-проверку.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| purchase-order-line-import | Open import from a draft order | implementation-driving | C1 | view-conflict | Нужны server action и wizard integration. |
| purchase-order-line-import | Reject import into a non-empty order | implementation-driving | C1 | procurement, security | Нужны UI visibility и повторяемый server-side empty-order guard на всех entry points. |
| purchase-order-line-import | Reject import outside the draft state | verification-only | C1 | procurement | Проверяет тот же lifecycle guard. |
| purchase-order-line-import | Parse a file with introductory rows | implementation-driving | C2 | bulk, uncertainty | Требует parser adapter и 1-based row handling. |
| purchase-order-line-import | Preserve physical XLSX row numbers | implementation-driving | C2 | bulk, uncertainty | Требует XLSX-ветку, которая не удаляет пустые физические строки. |
| purchase-order-line-import | Parse merged XLSX headers | implementation-driving | C2 | bulk, uncertainty | Нужна фильтрация unnamed physical columns без сдвига данных. |
| purchase-order-line-import | Stop before XLSX summaries | implementation-driving | C2 | bulk | Нужна явная граница непрерывного data block по пустой физической строке. |
| purchase-order-line-import | Select an XLSX worksheet | verification-only | C2 | uncertainty | Та же parser-options integration. |
| purchase-order-line-import | Reject an invalid file layout | verification-only | C2 | bulk | Error path общего parser adapter. |
| purchase-order-line-import | Reject a file without data rows | verification-only | C2 | bulk | Safety-check в том же parser flow. |
| purchase-order-line-import | Reload a source file after parsing | implementation-driving | C2 | view-conflict, bulk | Требует secondary action и перестроение transient mapping/preview. |
| purchase-order-line-import | Reuse a saved profile | implementation-driving | C3 | security | Нужны persistent models и копирование в wizard. |
| purchase-order-line-import | Save a mapping as a profile | implementation-driving | C3 | security | Нужны CRUD, constraints и configuration UI. |
| purchase-order-line-import | Prevent cross-company profile use | verification-only | C9 | security | Проверяет record rule/company checks. |
| purchase-order-line-import | Map recognized columns | implementation-driving | C4 | bulk | Нужны target schema, converters и preview rows. |
| purchase-order-line-import | Reject incomplete or duplicate mappings | verification-only | C4 | bulk | Validation path того же mapping engine. |
| purchase-order-line-import | Preview a valid import | implementation-driving | C4 | bulk | Нужен read-only validation/preview pipeline. |
| purchase-order-line-import | Preview reports row-specific errors | verification-only | C4 | bulk | Проверяет error aggregation общего pipeline. |
| purchase-order-line-import | Reject application of a stale preview | implementation-driving | C4 | bulk, security | Нужны digests/snapshot и invalidation. |
| purchase-order-line-import | Resolve by vendor product code | implementation-driving | C5 | bulk | Нужен batch exact-lookup по supplierinfo. |
| purchase-order-line-import | Continue through ordered lookup keys | verification-only | C5 | bulk | Проверяет порядок общего lookup engine. |
| purchase-order-line-import | Reject an ambiguous identifier | verification-only | C5 | bulk | Ambiguity branch того же lookup engine. |
| purchase-order-line-import | Reject an unmatched product | implementation-driving | C6 | bulk | Нужна unmatched policy профиля. |
| purchase-order-line-import | Create a standalone product | implementation-driving | C6 | bulk, security | Создание template/variant и precedence defaults. |
| purchase-order-line-import | Create a variant from an existing template configuration | implementation-driving | C6 | bulk, security, uncertainty | Standard combination validation и dynamic creation. |
| purchase-order-line-import | Reuse an existing variant combination | verification-only | C6 | bulk | Existing-combination branch того же resolver. |
| purchase-order-line-import | Reject an invalid variant combination | verification-only | C6 | bulk | Validation branch без отдельного механизма. |
| purchase-order-line-import | Populate an empty order | implementation-driving | C7 | procurement, bulk | Нужна атомарная координация product/supplierinfo и создания строк без удаления. |
| purchase-order-line-import | Roll back a failed application | implementation-driving | C7 | procurement, bulk | Определяет границу атомарного apply. |
| purchase-order-line-import | Retry after a failed application | verification-only | C7 | procurement | Следствие rollback и сохранения пустого PO. |
| purchase-order-line-import | Create a variant-specific supplier price | implementation-driving | C8 | bulk | Нужен supplierinfo upsert по exact key. |
| purchase-order-line-import | Update the matching supplier price | implementation-driving | C8 | bulk | Update branch общего upsert-механизма. |
| purchase-order-line-import | Preserve unrelated supplier price tiers | verification-only | C8 | bulk | Проверка точности key/domain. |
| purchase-order-line-import | Reject conflicting prices for one supplier-price key | verification-only | C8 | bulk | In-file conflict validation в том же механизме. |
| purchase-order-line-import | Reject an ambiguous existing supplier-price key | verification-only | C8 | bulk | Existing-data ambiguity branch upsert validation. |
| purchase-order-line-import | Authorized purchase user applies an import | implementation-driving | C9 | security | Нужны ACL, record rule и explicit checks. |
| purchase-order-line-import | Missing product-management permission | verification-only | C9 | security | Negative access path общего security design. |
| purchase-order-line-import | Reject company-incompatible data | verification-only | C9 | security | Company-domain/check path того же механизма. |
| purchase-order-line-import | Use a purchase order without import | verification-only | C1 | procurement | Regression-only: новый action не меняет standard flow. |

Классификация:

- `implementation-driving` — требует нового или изменённого production-поведения;
- `verification-only` — не требует отдельной реализации и проверяет общий механизм, стандартное поведение или отсутствие регрессии.

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Inherited PO view, action и wizard shell с lifecycle/empty-order guard | Open import; Reject non-empty; Reject outside draft; Standard behavior | 2 | Связанные UI и server-side guards на нескольких entry points без override state machine. |
| C2 | CSV adapter к `base_import`, physical-row XLSX adapter и file layout/reload options | Parse rows; Physical rows; Merged headers; Blank boundary; Worksheet; Invalid layout; Empty data; Reload | 6 | Разные row semantics CSV/XLSX, сохранение physical positions и безопасная перестройка transient state. |
| C3 | Persistent profile, mapping/lookup records и configuration views | Reuse profile; Save profile | 3 | Несколько связанных configuration records с constraints. |
| C4 | Mapping, type conversion, read-only preview, errors и stale detection | Map columns; Mapping errors; Valid preview; Row errors; Stale preview | 5 | Нетривиальный bulk validation pipeline с transient records и digest/snapshot. |
| C5 | Ordered batch exact product lookup | Vendor code; Ordered fallback; Ambiguity | 3 | Связь supplierinfo/product/company и безопасная ambiguity handling. |
| C6 | Unmatched policy, standalone creation и standard variant combination flow | Reject unmatched; Standalone product; Create/reuse/reject variant | 5 | Координация product template/variant/attributes с standard helpers и access checks. |
| C7 | Atomic server-side apply в пустой `order_line` | Populate empty order; Rollback; Retry | 3 | Координация создания products/prices/lines остаётся атомарной, но destructive unlink отсутствует. |
| C8 | Variant-specific supplierinfo validation/upsert | Create/update/preserve/conflict/ambiguity price scenarios | 3 | Exact multi-field key, batch conflicts и coordinated PO/supplier-price handoff. |
| C9 | Profile ACL/rule, access checks и company isolation | Cross-company profile; Authorized apply; Permission/company rejection | 2 | Связанные record rules и explicit checks без privilege escalation. |

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет.

### Дублирующиеся или пересекающиеся сценарии

- Нет дублей; verification-only сценарии намеренно проверяют отдельные границы общих механизмов.

### Недостающие сценарии

- Нет в согласованном scope. Поведение physical XLSX rows, merged headers, blank-row boundary, reload, непустого PO, пустого файла, stale preview и дублирующегося existing supplierinfo key явно покрыто.

### Недостаточно определённые или противоречивые сценарии

- Нет. Для standalone creation явно зафиксированы обязательный mapped name и precedence defaults; для variant creation — standard dynamic combination и запись variant identifiers.

## Расчёт трудозатрат

```text
32 implementation units × 1 час/unit = 32 часа
Исключительные дополнительные работы = 0 часов
Итого = 32 часа
```

- Discovery: 0 часов; стандартные extension points уже проверены.
- Миграция или обработка данных: 0 часов; addon новый.
- Production-like bulk/external coordination/special hardware: 0 часов.
- Необычная длительная или ручная проверка: 0 часов; обычные focused tests, module update, XML/view compilation и non-browser smoke уже входят в clusters.
- Другие исключительные конкретные работы: 0 часов.

## Стратегия проверки

### Автоматизированные тесты

- Требуются: да.
- Обоснование: bulk-импорт атомарно создаёт строки, товары/варианты, меняет supplierinfo и имеет security/multi-company риск; empty-order guard защищает от смешивания с ручными строками.
- Минимальный набор: parser/mapping/preview, exact lookup, оба creation mode, variant boundaries, empty-order guard на open/parse/preview/apply, atomic rollback/retry, supplierinfo key/upsert/conflicts, ACL/company/lifecycle и standard regression.

### Module update и smoke verification

- Проверить manifest/data order, ACL CSV, record rules, XML syntax, inherited view targets и external IDs.
- Обновить `purchase_import` в актуальной dev DB `odoo_tire` на свободном temporary HTTP port.
- Ручная non-browser smoke-проверка server actions и состояний wizard; browser automation не запускается.

## Основные факторы сложности

- Custom semantic mapping поверх standard CSV parser и physical-row XLSX adapter, а не прямой ORM import.
- Read-only preview с повторной validation, stale detection и атомарным заполнением пустого PO.
- Standard Odoo variant semantics (`always`, `dynamic`, exclusions, archived combinations).
- Exact variant-specific supplierinfo tier и in-file/existing-data ambiguity.
- ACL и multi-company без `sudo()` privilege escalation.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| bulk | Высокое: parsing, batch lookup, all-or-nothing update | File/row limits, batch searches, valid/invalid/large focused tests. |
| security | Высокое: product/supplier price creation и multi-company | Access tests для Purchase User/Manager/Product Manager и company boundaries. |
| procurement | Среднее: создаются draft purchase lines | Draft/empty-order guard и regression confirmation test; procurement methods не override. |
| uncertainty | Среднее: private CSV parser adapter, XLSX row semantics и dynamic variants | Characterization tests на точном Odoo 19 API и реальной XLSX fixture. |
| view-conflict | Низкое: одна insertion в PO form/config menu | Узкий XPath, module update и view compilation. |
| stock | Низкое: после confirmation lines попадут в standard stock flow | Import только в draft; standard confirmation regression. |
| accounting | Низкое: imported price позже попадёт в bill flow | Нет accounting overrides; standard confirmation/invoicing smoke. |

Flags `migration`, `external`, `mrp` и `legacy` к этому scope не применимы.

## Предположения

- Цена файла уже выражена в валюте PO и UoM строки.
- Supplier price key включает commercial partner, concrete variant, company, currency, UoM и `min_qty`; default `min_qty = 0`.
- Наличие product line, section или note блокирует импорт; import не удаляет существующие строки.
- Variant mode не создаёт attributes/values/attribute lines; новая комбинация допустима только для dynamic attributes.
- UI реализуется standard backend views без custom OWL.
- Файл и preview не хранятся как долгоживущий audit log.

## Исключено из оценки

- Создание/импорт шапки PO, merge строк и импорт в non-draft documents.
- Создание attribute catalog/template lines, fuzzy matching и arbitrary field mapping.
- Currency conversion, supplier discounts/date ranges, file attachments и durable import history.
- Background jobs, partial success и новая queue-зависимость.
- Browser-based automated tests и установка отсутствующих XLSX-зависимостей.

## Требуется discovery

- Нет.
- Обоснование: relevant Odoo 19 parser, purchase line, supplierinfo и variant extension points исследованы; неопределённость изолирована adapter/tests.

## Условия пересмотра оценки

- Нужен UI, близкий к standard import client action, вместо backend wizard.
- Нужно создавать missing attribute values/lines или variants для non-dynamic attributes.
- Нужны частичный success, merge/update existing lines, audit history или background processing.
- Цена файла имеет отдельную валюту/UoM semantics и требует conversion.
- Стандартный parser API окажется непригодным и потребуется отдельная parser subsystem.

## Фактический результат

Заполняется после реализации:

- Фактические часы:
- Отклонение от оценки:
- Причина отклонения:
- Фактические часы на unit:
- Изменения для будущей калибровки:
