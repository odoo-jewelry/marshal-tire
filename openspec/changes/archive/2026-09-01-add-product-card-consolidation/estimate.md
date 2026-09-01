# Оценка реализации

## Итог

- Всего сценариев: 26
- Implementation-driving сценариев: 15
- Verification-only сценариев: 11
- Implementation clusters: 6
- Implementation units: 21
- Fast path: нет
- Эмпирический размер: large
- Производительность: 1 час на implementation unit
- Базовая оценка: 21 час
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 20–24 часа активной работы мидл Odoo-разработчика
- Уверенность: средняя

Fast path неприменим: capability вводит новую security-managed модель, state-aware lifecycle нескольких подсистем, stock safeguards, computed/backend search и failure-recovery проверки. Обычные focused tests, static checks, module update и non-browser smoke включены в clusters.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| product-card-consolidation | Preview an eligible pair | implementation-driving | C1 | view-conflict | Нужны wizard, агрегированный preview и выбор canonical. |
| product-card-consolidation | Reject an invalid selection count | verification-only | C1 | security | Проверяет входную validation того же wizard. |
| product-card-consolidation | Cancel before confirmation | verification-only | C1 | — | Standard transient cancellation не выполняет business action. |
| product-card-consolidation | Reject multi-variant templates | implementation-driving | C2 | uncertainty | Нужна server-side проверка всех active/archived variants. |
| product-card-consolidation | Reject incompatible identity and inventory settings | implementation-driving | C2 | stock, uncertainty | Формирует основной compatibility matrix. |
| product-card-consolidation | Reject tracked products | verification-only | C2 | stock | Дополнительная ветвь общего eligibility analyzer. |
| product-card-consolidation | Reject current stock or reservations | implementation-driving | C2 | stock | Нужны точные company/location-aware quant checks. |
| product-card-consolidation | Revalidate before confirmation | implementation-driving | C2 | stock, concurrency | Confirmation повторно запускает analyzer по текущим данным. |
| product-card-consolidation | Preserve canonical scalar values | verification-only | C1 | accounting | Проверяет preview policy и отсутствие scalar writes. |
| product-card-consolidation | Combine non-conflicting configuration | implementation-driving | C3 | procurement, stock | Требуются allowlisted ORM handlers и dedup rules. |
| product-card-consolidation | Block unresolved configuration conflicts | implementation-driving | C3 | procurement, stock, uncertainty | Нужны natural keys и сравнение business values по типам rules. |
| product-card-consolidation | Redirect eligible draft documents | implementation-driving | C3 | procurement | Координация draft quotations/RFQs с сохранением line values. |
| product-card-consolidation | Preserve non-draft history | verification-only | C3 | stock, accounting | Проверяет allowlist и отсутствие generic FK updates. |
| product-card-consolidation | Open historical source product | verification-only | C4 | accounting | Проверяет standard active_test behavior и canonical link. |
| product-card-consolidation | Archive the duplicate | implementation-driving | C4 | stock | Нужны merge link, standard archive и ordering после transfer. |
| product-card-consolidation | Prevent accidental reactivation | implementation-driving | C4 | security | Нужна серверная lifecycle guard для template/variant. |
| product-card-consolidation | Resolve an alternative internal reference | implementation-driving | C5 | uncertainty | Нужны alias-aware backend search и exact resolver. |
| product-card-consolidation | Resolve an alternative barcode | verification-only | C5 | uncertainty | Повторяет resolver pattern для второго identifier type. |
| product-card-consolidation | Preserve supplier product resolution | implementation-driving | C3 | procurement | Supplierinfo перенос и conflict policy обеспечивают existing import lookup. |
| product-card-consolidation | Consolidate another duplicate later | verification-only | C4 | migration | Проверяет накопление aliases и отсутствие merge chain. |
| product-card-consolidation | Reject an unauthorized user | implementation-driving | C6 | security | Нужны group, ACL и explicit API guard. |
| product-card-consolidation | Confirm an irreversible action | implementation-driving | C1 | security, view-conflict | Нужен отдельный confirmation step без ранних writes. |
| product-card-consolidation | Record a successful consolidation | implementation-driving | C4 | security | Нужен один audit message с actor/source/summary. |
| product-card-consolidation | Roll back a failed consolidation | verification-only | C6 | stock, procurement | Проверяет standard transaction boundary всего service. |
| product-card-consolidation | Retry after a failed attempt | verification-only | C6 | concurrency | Использует atomic rollback и C2 revalidation без отдельного механизма. |
| product-card-consolidation | Use an ordinary product | verification-only | C5 | regression | Проверяет отсутствие влияния aliases/guards на обычные products. |

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Transient wizard, preview lines, bound action и final confirmation | Preview; selection count; cancellation; scalar policy; confirmation | 2 | Один связный UI/server entry point с простыми views, но нетривиальным preview. |
| C2 | Единый eligibility analyzer и повторная проверка текущего состояния | Multi-variant; compatibility; tracking/lots; quants/reservations; stale preview | 3 | Batch checks затрагивают Product и Stock и должны одинаково работать из UI/API. |
| C3 | Allowlisted ORM handlers для configuration и draft business references | Configuration merge/conflicts; draft documents; history preservation; supplier resolution | 5 | Несколько record types в Purchase, Sales и Stock с natural-key dedup и неизменной историей. |
| C4 | Canonical metadata lifecycle, alias accumulation, archive/unarchive guard и audit | Archive; historical navigation; reactivation; repeated merge; audit | 3 | Согласованное состояние template/variant и повторные операции без удаления source. |
| C5 | Alias-aware backend resolver, display-name search и `purchase_import` integration | Internal reference; barcode; ordinary product regression | 3 | Нетривиальный search extension с company scope, ambiguity и сохранением import priority. |
| C6 | Dedicated permission boundary, controlled administrative writes и atomic service | Unauthorized access; rollback; retry | 5 | Security и failure recovery охватывают несколько подсистем и требуют негативных API/multi-company tests. |

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет. Combined compatibility scenario перечисляет один класс preflight settings и возвращает единый observable blocker list.

### Дублирующиеся или пересекающиеся сценарии

- `Revalidate before confirmation`, `Roll back a failed consolidation` и `Retry after a failed attempt` пересекаются по failure path, но фиксируют разные обязательства: stale input, transaction atomicity и повторный запуск. Объединять их не требуется.
- Alias scenarios используют общий resolver, но отдельно фиксируют семантику internal reference, barcode и supplier-specific identifier.

### Недостающие сценарии

- Нет для подтверждённого scope. POS alias scanning, physical history merge и stock transfer явно исключены design.

### Недостаточно определённые или противоречивые сценарии

- Полный перечень supported configuration natural keys является design-level allowlist; до реализации нужно подтвердить actual Odoo 19 fields для каждого handler, но observable conflict policy определена.
- «Supported backend lookup» намеренно не включает POS frontend; это явно указано в design и не противоречит specification.

## Расчёт трудозатрат

- Сумма implementation units: 21
- Hours per unit: 1
- Базовые часы: 21
- Discovery: 0
- Миграция или обработка данных: 0
- Production-like bulk/external coordination/special hardware: 0
- Необычная длительная или ручная проверка: 0
- Другие исключительные конкретные работы: 0
- Итоговый диапазон: 20–24 часа

Диапазон отражает обычную вариативность реализации вокруг базовых 21 часа; отдельный multiplier за addons или risk flags не применяется.

## Стратегия проверки

### Автоматизированные тесты

- Требуются: да.
- Обоснование: lifecycle изменяет Product, Purchase, Sales и Stock, вводит новую security boundary, computed/exact search и rollback behavior.
- Минимальный набор:
  - eligibility и stale preview;
  - configuration dedup/conflict matrix;
  - draft versus immutable history;
  - aliases, ambiguity и `purchase_import` preview/apply;
  - archive/unarchive/repeated merge;
  - permissions, controlled `sudo()` и cross-company denial;
  - forced mid-operation failure, rollback и retry;
  - unchanged ordinary product behavior.

### Module update и smoke verification

- Проверить Python syntax/imports, manifest dependencies/data order, XML/external IDs, ACL и group privilege.
- Выполнить install/update `product_card_consolidation` в test DB и focused tagged tests.
- Статически проверить inherited views и bound server action.
- Вручную проверить wizard preview/confirmation, archived ribbon/canonical link и обновление POS catalog после reload; browser automation не выполнять.

## Основные факторы сложности

- Разная семантика ссылок на `product.template` и `product.product`.
- Natural-key conflicts в supplierinfo, pricelist, orderpoints, packaging и stock configuration.
- Совместное сохранение immutable history и перевод разрешённых draft references.
- Alias search должен сохранять standard domain, limit, company isolation и ambiguity behavior.
- Административная операция должна быть одновременно полномочной, ограниченной и атомарной.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| stock | Ошибочная работа с quant/reservation или archived source может нарушить операции | Нулевой stock invariant, отсутствие quant writes, state matrix tests |
| procurement | Draft/confirmed граница и supplierinfo conflicts | Явные state domains, ORM handlers, RFQ/import tests |
| accounting | История и company-dependent costs не должны меняться | Accounting references excluded, canonical scalar regression tests |
| security | Controlled `sudo()` может расширить область записи | Dedicated group, exact company checks, allowlist и negative API tests |
| uncertainty | Полный набор fields natural key различается по models | Reinspection actual Odoo 19 fields и focused handler fixtures |
| view-conflict | Product views расширяются несколькими установленными addons | Stable XPath/action binding и module update/XML validation |
| concurrency | Preview может устареть до confirm | Полная повторная validation непосредственно в business action |

## Предположения

- Объединяются только два active single-variant templates.
- Обе карточки имеют exact одинаковый `company_id`, UoM и storage semantics.
- Tracking отсутствует, lots отсутствуют, current/reserved stock равен нулю.
- Canonical scalar values всегда побеждают; пользователь не выбирает значения отдельных полей.
- Подтверждённые и завершённые документы продолжат использовать archived source.
- `purchase_import` остаётся установленным и его lookup contract сохраняется.

## Исключено из оценки

- Перенос или оценка складских остатков, FIFO/AVCO и valuation/accounting entries.
- Изменение confirmed/done/posted history или consolidated standard reports.
- Multi-variant mapping, lots/serials и MRP-specific handlers.
- POS frontend alias dataset/scanning и browser automation.
- External ID remapping, generic reference scanning и сторонние addon handlers.
- Production data cleanup или выполнение реальных merge operations.

## Требуется discovery

- Нет.
- Обоснование: архитектурный подход и Odoo extension points определены. Focused reinspection natural keys является обычной частью cluster C3, а не отдельным discovery.

## Условия пересмотра оценки

- Потребуется физически объединять исторические `product_id` или отчёты.
- Появится требование переносить остатки, резервы, lots/serials или valuation.
- Нужно поддержать multi-variant templates либо более двух карточек за операцию.
- Старые aliases должны сканироваться в POS frontend.
- Требуется перенос arbitrary third-party references или external IDs.
- Configuration conflicts нужно разрешать интерактивным field-by-field wizard вместо блокировки.

## Фактический результат

Заполняется после реализации:

- Фактические часы:
- Отклонение от оценки:
- Причина отклонения:
- Фактические часы на unit:
- Изменения для будущей калибровки:
