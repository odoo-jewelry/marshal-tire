# POS Cost Recompute Specification

> [!abstract] Пересчёт себестоимости POS
> Позволяет руководителю POS проверить и пересчитать себестоимость исторических чеков с сохранением причин, источников и результатов операции.
>
> **Использование:**
>
> В административном списке чеков «Point of Sale → Orders → Orders» доступно действие «Actions → Recompute Costs» для выбранных чеков. Меню «Point of Sale → Cost Recomputation» открывает историю и создание операции по периоду. В форме чека добавлена кнопка «Cost History», открывающая связанные операции; существующие поля чека не изменены и не удалены.
>
> В новой форме операции доступны компания, способ отбора «Selected Orders» или «Date Interval», поля «Orders», «From (inclusive)», «To (exclusive)», «Point of Sale», «Products» и режим «Zero Saved Costs Only» либо «All Matching Lines». Поле «Reason» задаёт причину применения, а «I acknowledge zero source costs» подтверждает допустимость нулевых источников. Отбор охватывает подходящие строки одной компании и закрытых смен без фиксированного предела их количества.
>
> Кнопка «Preview Costs» показывает прежнюю и предлагаемую себестоимость, изменение маржи, источники, причины пропуска и итоги по валютам. В детализации доступны связанные движения, признаки завершённости расчёта, фактический результат и связанные продажи или возвраты вне выборки. «Apply Reviewed Costs» применяет подтверждённые суммы с причиной; «Cancel Operation» отменяет операцию до применения. Руководитель POS может удалить черновую или отменённую операцию доступной компании вместе с её предварительными расчётами без изменения чеков и складских движений. История содержит состояние, автора и время применения, счётчики изменённых, неизменных, завершённых без изменения суммы и пропущенных строк; применённые результаты защищены от редактирования и удаления.
>
> Например, для чеков с нулевой сохранённой себестоимостью можно проверить доступные источники и применить предложенные суммы. Для ошибочной ненулевой суммы выбирают «All Matching Lines». Услуги и товары со стандартной себестоимостью используют текущую стоимость компании, а товары FIFO и средней стоимости — существующую складскую оценку. Нулевая оценка требует отдельного подтверждения; отсутствующие или неоднозначные источники приводят к объяснимому пропуску. При изменении источников после просмотра требуется новый просмотр. Повторное применение уже выполненной операции возвращает её результат. Маржа чеков и отчёта POS обновляется; складская оценка, бухгалтерские документы и невыбранные чеки сохраняются.
^feature-card

## Purpose

Allow authorized POS managers to recompute historical POS line costs through a reviewed, bounded, auditable operation using supported standard Odoo cost sources.

## Requirements

### Requirement: Explicit bounded selection

The system SHALL provide a cost-recomputation action from the administrative POS order list and an operation-history entry. An operation MUST belong to one authorized company. In ordinary modes, users SHALL select explicit orders or a bounded order-date interval, optionally narrowed by POS configurations and products. With historical stock write-off installed, the explicit historical mode SHALL instead use selected completed historical documents to determine affected products and the earliest inclusive date through the preview cutoff; additional order, POS and product filters SHALL NOT narrow that scope. The explicit consolidated-history selection SHALL instead use applied full-history consolidations to determine the canonical products and earliest affected issue through the preview cutoff. Historical-document selection SHALL include any earlier issue boundary required by full consolidation of its products. Both history selections SHALL use all matching costs and SHALL NOT be narrowed by ordinary filters. The default ordinary mode SHALL select only lines with zero saved cost; an explicit all-lines mode SHALL also consider incorrect nonzero costs. The system MUST NOT impose a fixed maximum number of selected lines. Each operation SHALL include every matching line, SHALL freeze its line selection at preview, and MUST NOT silently truncate or expand that selection.

#### Scenario: S01 Select historical orders by filters
- **WHEN** a manager previews an operation for a company, date interval, POS configuration and product
- **THEN** only lines matching the intersection of those criteria are selected
- **AND** displayed date boundaries use the user's timezone with an inclusive start and exclusive end

#### Scenario: S02 Recompute a nonzero saved cost
- **GIVEN** a selected line has an incorrect nonzero saved cost
- **WHEN** the manager selects all-lines mode and previews it
- **THEN** the line is evaluated for recomputation
- **AND** the default zero-only mode would exclude it

#### Scenario: S03 Respect explicit order selection
- **WHEN** the manager starts from explicitly selected orders and applies additional product filters
- **THEN** the operation contains only matching lines of those orders
- **AND** it never expands to other orders matching the same dates or products

#### Scenario: S04 Reject a missing or invalid selection scope
- **WHEN** an operation lacks the required source selection for its mode or has invalid date boundaries
- **THEN** preview is rejected with an actionable explanation
- **AND** no order cost is changed and no partial selection is presented as complete

#### Scenario: S40 Process a selection exceeding the former line limit
- **GIVEN** more than 1000 eligible lines match the explicit order selection or bounded date interval
- **WHEN** the manager previews and applies the reviewed operation
- **THEN** every matching line is included and processed under the ordinary eligibility rules
- **AND** the operation neither rejects nor truncates the selection because of its line count

### Requirement: Reviewable cost proposal

Preview SHALL leave POS business records unchanged and show each selected line's order, product, signed quantity, currency, previous cost, proposed cost when available, margin difference, cost source and result status. Statuses SHALL distinguish a proposed change, unchanged values, a required acknowledgement and a skipped line with a reason. Totals SHALL be grouped by currency and SHALL distinguish cost changes from previously incomplete calculation markers. An empty or entirely skipped ordinary POS selection SHALL NOT offer application. Historical and consolidated-history modes MAY apply a reviewed nonempty stock plan even when no POS lines are affected; unsupported related POS sources SHALL reject the whole history plan rather than be silently skipped. A zero proposed unit cost SHALL require explicit acknowledgement before that line may be applied.

#### Scenario: S05 Preview before applying
- **WHEN** a manager previews an eligible operation
- **THEN** previous and proposed costs, margin differences and source explanations are displayed
- **AND** no saved POS cost or calculation-completion marker changes

#### Scenario: S06 Acknowledge a zero source
- **GIVEN** a selected line has a supported source with zero unit cost
- **WHEN** the manager attempts to apply without acknowledging the zero result
- **THEN** application is rejected
- **AND** the interface explains that recomputation cannot repair the underlying zero source

#### Scenario: S07 Report an empty or skipped selection
- **WHEN** ordinary POS preview finds no selected lines or every selected line is ineligible
- **THEN** the interface displays the empty result or individual skip reasons
- **AND** application is unavailable

### Requirement: Supported standard cost semantics

For eligible lines outside stock-valued FIFO and average-cost products, recomputation SHALL use the current product cost of the order company. For eligible stock-valued FIFO and average-cost lines, it SHALL use existing completed stock valuation sources and the standard weighted unit-cost calculation. Cost amounts SHALL preserve the signed POS quantity and use standard conversion from cost currency to order currency at the order date without intermediate rounding. Ordinary recomputation MUST NOT substitute current product cost for unavailable or ambiguous stock valuation and MUST NOT claim to restore historical acquisition costs. Explicit historical mode SHALL use the supported standard historical FIFO calculation for reviewed subsequent issues, without fabricating receipt costs or missing opening quantities. Product cost methods and units are interpreted as currently configured; historical configuration changes are outside automatic reconstruction.

#### Scenario: S08 Recompute from current standard cost
- **GIVEN** a line sold two units, its saved cost is zero, its order currency equals cost currency, and its product now has standard unit cost 40
- **WHEN** the reviewed operation is applied
- **THEN** the saved line cost becomes 80 and its calculation is marked complete

#### Scenario: S09 Preserve service cost semantics
- **GIVEN** an eligible service line has no stock movement and a current company unit cost of 15
- **WHEN** two sold units are recomputed in the same currency
- **THEN** the saved line cost becomes 30 without requiring a stock movement

#### Scenario: S10 Use existing FIFO or average valuation
- **GIVEN** eligible stock movements value two units at a total of 60 while the product card shows a unit cost of 50
- **WHEN** a corresponding two-unit FIFO or average-cost sale is recomputed
- **THEN** its cost becomes 60 rather than 100

#### Scenario: S11 Convert cost in the order context
- **GIVEN** cost and order currencies differ and the applicable rate differs between the order date and today
- **WHEN** a line is recomputed
- **THEN** its company-specific source is converted at the order-date rate without intermediate rounding
- **AND** amounts in different currencies are not added into an unlabeled total

### Requirement: Stock-source resolution and lifecycle eligibility

Only paid or posted orders in closed POS sessions SHALL be eligible. Stock-valued FIFO and average-cost lines MUST have a supported completed valuation source with positive valued quantity and no relevant unfinished movement. Direct order movements SHALL take precedence over session movements. If there are no direct movements and normal stock processing occurred at session closure, the operation SHALL consider the complete relevant session-level source for the product, including movements attributable to unselected orders. It SHALL label the result as a session-level weighted cost, not an exact historical line allocation. A source containing opposite sale and return directions, inconsistent direction, unavailable valuation, or an unprovable association SHALL cause the affected line to be skipped. The system SHALL NOT create or finish stock movements to make a line eligible.

#### Scenario: S12 Resolve aggregate session movements
- **GIVEN** a closed session has only outgoing completed movements for a selected product, totalling four valued units and value 100, with no direct picking on the selected order
- **WHEN** a one-unit sale from that session is recomputed
- **THEN** its cost becomes 25 in the same currency
- **AND** preview identifies the session-level weighted source, including quantities from unselected orders

#### Scenario: S13 Prefer direct order movements
- **GIVEN** an order has its own completed movements and its session also contains other movements of that product
- **WHEN** its cost is recomputed
- **THEN** only its supported direct source is used without adding the session source

#### Scenario: S14 Skip mixed sale and return stock sources
- **GIVEN** the candidate source for a product includes both outgoing sales and incoming returns
- **WHEN** a selected line of that product is previewed
- **THEN** the line is skipped with an ambiguous-source explanation
- **AND** restricting selection to sales alone does not hide the return movements from that check

#### Scenario: S15 Skip an open session
- **WHEN** a paid order in an open or closing session is selected
- **THEN** its lines are skipped with a session-not-closed explanation
- **AND** the operation neither closes the session nor marks deferred costs complete

#### Scenario: S16 Skip incomplete or missing valuation
- **WHEN** a stock-valued line has relevant unfinished delivery movements, no provable completed source, or zero valued quantity
- **THEN** the line retains its saved cost and completion marker
- **AND** the result explains the missing or incomplete source

#### Scenario: S17 Exclude draft and cancelled orders
- **WHEN** a draft or cancelled order is selected
- **THEN** its lines are reported as ineligible without changing the order

### Requirement: Explicit return limitations

Supported returns SHALL retain standard signed-cost semantics. A standard-cost return SHALL use current company product cost; a stock-valued return SHALL use its supported existing return valuation source. Recalculation SHALL NOT invent a link to an original sale movement or guarantee that sale and return costs cancel when their sources differ. Linked sale or return lines outside the frozen selection SHALL remain unchanged and SHALL be identified as related records outside the operation. The first version SHALL skip the special deferred-delivery branch that would substitute a zero movement cost with product cost or original POS line cost, explaining that it requires separate review.

#### Scenario: S18 Recompute a partial standard-cost return
- **GIVEN** a selected return contains quantity minus one for a product with current standard unit cost 40 in the same currency
- **WHEN** the return is recomputed
- **THEN** its cost becomes minus 40 regardless of the originally saved sale cost
- **AND** preview explains the current-cost basis

#### Scenario: S19 Reuse a return movement valuation
- **GIVEN** a completed return movement values one returned unit at 30 using its existing original-movement association
- **WHEN** the corresponding eligible FIFO or average-cost return is recomputed in the same currency
- **THEN** its saved cost becomes minus 30 without modifying either movement

#### Scenario: S20 Keep unselected linked orders unchanged
- **GIVEN** a selected sale has a linked return outside the frozen selection
- **WHEN** the operation is previewed and applied
- **THEN** the related return is identified as outside the operation and remains unchanged
- **AND** no claim is made that their resulting margins necessarily cancel

#### Scenario: S21 Skip deferred-delivery zero-cost substitution
- **GIVEN** a deferred-delivery sale or return would require substitution of a zero movement cost
- **WHEN** it is previewed
- **THEN** the affected line is skipped with a specific unsupported-fallback explanation

### Requirement: Observable handling of unsupported structures

The first version SHALL skip zero-quantity lines, POS combo structures, manufacturing kits, and known project correction chains rather than inventing their cost allocation. This exclusion SHALL also cover session-level stock sources affected by project corrections. Archived products SHALL remain selectable through historical orders and SHALL be handled normally when all other conditions are supported. Other independently eligible selected lines MAY be applied, provided every skip is visible before confirmation and retained in the result.

#### Scenario: S22 Report unsupported structures
- **WHEN** selected lines include zero quantities, combo structures or manufacturing kits
- **THEN** those lines are skipped with specific reasons
- **AND** ordinary supported lines remain available for review

#### Scenario: S23 Isolate project correction chains
- **GIVEN** project corrections affect a selected order or its candidate shared stock source
- **WHEN** the operation is previewed
- **THEN** the affected lines are skipped without changing correction history or allocations

#### Scenario: S24 Process an archived product
- **GIVEN** an eligible historical line references an archived product
- **WHEN** it is selected through its order
- **THEN** it can be recomputed using the same eligibility and cost rules as an active product

### Requirement: Atomic reviewed application

Application SHALL require a nonempty reason, an explicit confirmation and a current server-generated preview. It MUST revalidate authorization, selected records, source identity and relevant values before any cost update. An external change to a source, cost, quantity, lifecycle condition or conversion input SHALL invalidate the whole preview. In explicit stock-repair or historical mode, only the fixed stock-value changes included in the reviewed plan MAY be applied before POS recomputation; they are authorized parts of that same transaction, not external stale-preview changes. The operation SHALL apply only its reviewed eligible lines in one transaction; an unexpected failure MUST roll back all cost, completion-marker and success-history changes. No intermediate commits or silent runtime skips are permitted. Parallel or repeated requests for the same applied operation SHALL return its existing result, and overlapping operations SHALL not overwrite changes using stale previews.

#### Scenario: S25 Apply a reviewed mixed selection
- **GIVEN** preview contains eligible and explicitly skipped lines and all required acknowledgements are present
- **WHEN** the manager confirms with a reason
- **THEN** only reviewed eligible lines are applied and skipped lines remain unchanged
- **AND** the result counts changed, unchanged, completion-only and skipped lines separately

#### Scenario: S26 Reject stale preview data
- **GIVEN** a relevant product cost, valuation source, order quantity, saved cost or exchange-rate input changed after preview
- **WHEN** application is requested
- **THEN** the entire operation is rejected without cost updates and requires a fresh preview

#### Scenario: S27 Roll back a runtime failure
- **WHEN** a required write or access check fails after processing has started
- **THEN** all updates of the operation are rolled back
- **AND** no successful application history is recorded

#### Scenario: S28 Retry or concurrently submit the same operation
- **WHEN** the same operation receives repeated or concurrent application requests
- **THEN** at most one request performs the updates
- **AND** another caller receives the existing result or a retryable busy response while processing is still active
- **AND** retry after success returns the same applied result without duplicate changes or history

#### Scenario: S29 Reject overlapping stale operations
- **GIVEN** two operations preview the same line and the first changes its saved cost or completion marker
- **WHEN** the second operation attempts application
- **THEN** the second is rejected as stale rather than overwriting the first result

#### Scenario: S30 Cancel before application
- **WHEN** a manager cancels a draft or previewed operation
- **THEN** no POS cost or stock value changes and the cancelled operation cannot be applied

#### Scenario: S31 Recompute again with unchanged inputs
- **GIVEN** a previous operation completed and all relevant inputs remain unchanged
- **WHEN** a new all-lines operation previews the same lines
- **THEN** their values are reported as unchanged without cumulative cost or margin drift

### Requirement: Authorization and protected history

Creating previews and applying operations SHALL require POS manager permission and normal access to all affected records and cost sources. Every operation and detail SHALL be restricted to its authorized company. Application SHALL retain the acting user, application time, reason, reviewed selection, sources, before and after costs and markers, and skipped reasons. Applied operations and their details SHALL be immutable through ordinary editing, deletion, copying, import and direct requests; duplicated drafts SHALL contain only fresh editable selection criteria. Direct calls MUST enforce the same rules as the interface and MUST NOT trust client-supplied computed results.

An authorized POS manager SHALL be allowed to delete draft and cancelled operations in an authorized company, subject to existing access rules for their details. Deletion SHALL remove the operation and its POS and stock preview details together without changing POS business records, stock movements or stock values. Reviewed and applied operations MUST NOT be deleted; a reviewed operation SHALL require cancellation first. A deletion request containing any protected operation MUST fail without deleting any operation or detail. Preview details SHALL remain server-managed and MUST NOT allow direct editing or deletion, including when their operation is cancelled. The deletion permission MUST NOT weaken protection of applied audit evidence.

#### Scenario: S32 Reject an unauthorized direct request
- **WHEN** a non-manager or a manager lacking required record access directly requests preview or application
- **THEN** the request fails without exposing unavailable source costs or changing records

#### Scenario: S33 Preserve company isolation
- **WHEN** an operation mixes orders from different companies or references an unauthorized company
- **THEN** it is rejected
- **AND** an authorized single-company operation always reads that order company's product cost

#### Scenario: S34 Inspect applied history
- **WHEN** an authorized manager opens an applied operation
- **THEN** its author, time, reason, selected lines, sources, previous and resulting values and skip reasons remain available

#### Scenario: S35 Protect results from editing and forgery
- **WHEN** ordinary editing, import, copying or a direct request attempts to forge preview amounts, alter applied history or reapply an applied copy
- **THEN** it is rejected or creates only a fresh draft containing selection criteria
- **AND** no forged cost update is applied

#### Scenario: S41 Delete a cancelled operation with preview details
- **GIVEN** an authorized manager has cancelled an operation with POS or stock preview details
- **WHEN** the manager deletes the operation
- **THEN** the operation and its preview details are deleted together
- **AND** POS costs, calculation-completion markers, stock movements and stock values remain unchanged

#### Scenario: S42 Preserve deletion boundaries
- **WHEN** an authorized manager deletes draft or cancelled operations in an authorized company
- **THEN** deletion is allowed subject to existing access rules
- **AND** a request containing a reviewed or applied operation is rejected without deleting any operation or detail

#### Scenario: S43 Enforce deletion authorization
- **WHEN** a non-manager or a manager without access to the operation company directly requests deletion of a draft or cancelled operation
- **THEN** deletion is rejected and the operation and its details remain available to authorized users

#### Scenario: S44 Reject direct deletion or editing of preview details
- **WHEN** a direct request attempts to edit or delete a POS or stock preview detail, including a detail of a cancelled operation
- **THEN** the request is rejected
- **AND** removing preview details with a cancelled operation is permitted only through the server-managed operation deletion

### Requirement: POS reporting and operational continuity

After application, standard POS line and order margins and the POS sales-analysis report SHALL reflect updated saved costs using their existing formulas. Quantities, sales prices, discounts, taxes, totals, payments, invoices, accounting entries, stock movement identities, dates and dimensions, receipt values and product costs MUST remain unchanged by the operation. Ordinary recomputation MUST also leave all stock valuation amounts unchanged. Explicit stock-repair mode MAY change only the reviewed eligible zero-valued outgoing movements under the stock-repair requirements, followed by recomputation of their fully selected POS lines. Explicit historical mode MAY also update reviewed nonzero outgoing values from the earliest selected historical consumption, followed by all supported related POS costs. Both modes MUST NOT create stock movements or financial postings. Installation or upgrade SHALL NOT trigger historical recomputation. Ordinary POS sale, refund, invoicing and session-closing workflows SHALL retain their existing behavior when this feature is not invoked.

#### Scenario: S36 Refresh standard POS margin reporting
- **GIVEN** a same-currency two-unit sale has untaxed revenue 120 and its reviewed cost changes from zero to 80
- **WHEN** the operation completes and the order and sales analysis are refreshed
- **THEN** their margin for that sale is 40 using the standard report formulas

#### Scenario: S37 Preserve invoiced order accounting and stock
- **GIVEN** an eligible historical order has a posted invoice and completed stock processing
- **WHEN** its POS cost is recomputed
- **THEN** invoice, accounting, payments, stock quantities, stock valuation and product costs remain unchanged
- **AND** the original sale quantities, prices, discounts, taxes and totals are preserved

#### Scenario: S38 Preserve ordinary workflows
- **WHEN** ordinary POS sales, returns, invoicing and session closures run without invoking recomputation
- **THEN** those workflows retain standard Odoo behavior

#### Scenario: S39 Install and upgrade without recomputation
- **WHEN** the module is installed or upgraded on a database containing historical POS orders
- **THEN** no historical POS cost is rewritten by installation or upgrade

### Requirement: Server-owned source versions during POS synchronization

Source-version counters used to detect stale recomputation previews SHALL remain server-managed and SHALL NOT be included in POS order loading fields, field metadata or synchronization responses. Valid POS order synchronization SHALL ignore any client-supplied source-version counter, including empty, stale or arbitrary values sent by an already open or offline client. Ordinary cashiers MUST be able to create, save and pay otherwise valid orders without recomputation-manager permission. Synchronization MUST preserve server-controlled source tracking and stale-preview protection. Direct creation or editing that assigns a source-version counter, including through a supplied default value, MUST remain forbidden. These rules SHALL NOT bypass ordinary order validation, record access or company restrictions.

#### Scenario: S45 Exclude source versions from POS order data
- **WHEN** an authorized cashier loads POS order fields and records or receives synchronized orders
- **THEN** source-version counters are absent from the field metadata and returned order data
- **AND** standard order fields required for checkout remain available

#### Scenario: S46 Pay a new order containing a client source version
- **GIVEN** a cashier has ordinary POS access without recomputation-manager permission
- **WHEN** the cashier submits an otherwise valid paid order containing an empty or arbitrary source-version counter
- **THEN** the sale follows standard payment and cost processing without a source-version access error
- **AND** the supplied counter is ignored and source versions remain controlled by the server

#### Scenario: S47 Retry and pay a draft from an already open client
- **GIVEN** a draft order has been synchronized and a subsequent source change has advanced its server-owned version
- **WHEN** an already open or offline POS client resends the draft and later pays it with an outdated or arbitrary source-version counter
- **THEN** the existing order is updated and paid through the standard workflow
- **AND** the client counter does not reset or replace server-owned versions or disable source-change tracking

#### Scenario: S48 Reject direct source-version assignment
- **WHEN** a direct creation or editing request assigns a source-version counter, including an empty value or a supplied default
- **THEN** the assignment is rejected and existing source-version data remains unchanged

### Requirement: Manual valuation of fully consolidated history

An authorized user SHALL be able to open the existing recomputation tool from an applied full-history consolidation. Preview SHALL include the canonical products' real affected outgoing movements from the earliest affected issue through a fixed preview cutoff, including nonzero stored values and supported related POS costs outside the initial selection. It SHALL use standard historical FIFO over original receipts and SHALL exclude retired consolidation transfer pairs. Applying the reviewed plan MUST update stock values before POS costs atomically, preserving before/after evidence, quantities, revenue, payments, debts and posted accounting entries. Consolidation SHALL NOT invoke this operation automatically or add pending-recomputation flags. Existing permissions, period checks, unsupported-source rejection and stale-preview protection SHALL apply. Ordinary cost recomputation and zero-stock-value repair SHALL retain their existing semantics.

#### Scenario: C01 Start from a completed merge
- **WHEN** an authorized user opens manual recomputation from an applied full-history consolidation
- **THEN** the existing tool selects its canonical products and earliest affected issue through the preview cutoff
- **AND** no cost changes until the reviewed plan is applied

#### Scenario: C02 Recompute nonzero merged costs
- **GIVEN** the combined original receipt sequence changes a subsequent issue's stored nonzero cost
- **WHEN** the user applies the reviewed consolidated-history plan
- **THEN** that issue and every other affected supported issue are revalued using standard historical FIFO before their related POS costs
- **AND** real receipt values, quantities and commercial amounts remain unchanged

#### Scenario: C03 Exclude retired transfer receipts
- **GIVEN** an old consolidation pair has been retired by full-history conversion
- **WHEN** a consolidated-history cost plan is calculated
- **THEN** only the real original receipts contribute to the FIFO sequence and the retired pair is absent from active valuation

#### Scenario: C04 Reject stale plans
- **GIVEN** sources change after preview
- **WHEN** application is requested
- **THEN** the plan is refused with an actionable reason and no partial stock or POS cost changes

#### Scenario: C07 Reject unsupported valuation
- **GIVEN** required valuation would touch an unsupported or protected history
- **WHEN** consolidated-history recomputation is previewed
- **THEN** the entire plan is rejected with the unsupported records identified

#### Scenario: C05 Apply a stock-only plan
- **GIVEN** a valid consolidated-history plan has affected stock issues and no related POS lines
- **WHEN** the user applies it
- **THEN** reviewed stock values are updated with audit evidence without requiring a POS sale

#### Scenario: C06 Preserve ordinary cost tools
- **WHEN** users run ordinary POS cost recomputation or zero-stock-value repair without consolidated-history selection
- **THEN** their existing scope, permissions and valuation restrictions remain unchanged
