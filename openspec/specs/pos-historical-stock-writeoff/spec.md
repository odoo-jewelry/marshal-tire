# POS Historical Stock Write-off Specification

> [!abstract] Историческое списание по чеку
> Регистрирует расход товаров по продажам до запуска Odoo с привязкой к существующей старой смене без выручки и оплат.
>
> **Использование:**
>
> В форме чернового или отменённого чека кнопка «Историческое списание» открывает складской черновик. В нём можно изменить товары и количества, выбрать «Старая смена», проверить «Историческая дата» и заполнить «Основание». Подходит существующая закрытая смена той же кассы и компании; первоначально предлагается время её закрытия.
>
> Кнопка «Провести списание» уменьшает остатки один раз. Исходный чек сохраняет прежние дату, смену, строки и состояние. В формах чека и выбранной смены появляется переход «Исторические списания». Складской документ показывает исходный чек, старую смену, историческую дату, фактическую дату выполнения и исполнителя. Существующие колонки списков чеков и смен сохраняются.
>
> После одного или нескольких переносов кнопка «Пересчитать последующую себестоимость» открывает существующий инструмент пересчёта в режиме «Исторические списания». Можно выбрать несколько проведённых документов: самая ранняя дата и их товары определяют всю последующую историю до времени просмотра. Просмотр показывает старые и новые суммы склада и связанных завершённых чеков, включая ненулевую себестоимость. «Применить себестоимость склада и чеков» сначала обновляет складские оценки, затем себестоимость чеков. Основание, автор и результаты сохраняются в истории. Следующий перенос можно обработать новым пересчётом; прежний результат остаётся доступен через «Cost History» исходного чека.
>
> Например, отменённый чек с нулевыми ценами можно использовать для списания товаров в старой смене, не оплачивая его. Несколько таких списаний можно затем совместно пересчитать от самого раннего. Оба шага выполняются вручную; автоматического пересчёта и отдельных отметок о его необходимости нет.
>
> Нужны отдельное разрешение на исторические списания, зарегистрированный остаток на выбранную дату и поддержанная история: собственные товары без партий и серийных номеров, FIFO и периодическая оценка. Недостаток в прошлом или позднее, чужие резервы, возвраты, сложные перемещения и заблокированные периоды вызывают объяснимый отказ. Недостающие приходы не создаются. Подготовку можно отменить, проведённое списание нельзя вернуть в черновик или переписать.
^feature-card

## Purpose

Provide a reusable way to record stock consumption for sales made before Odoo adoption, using an existing unposted receipt as the editable source and an existing historical POS session as the business reference, without recording sales revenue or customer payments.

## Requirements

### Requirement: Preparation from an eligible historical receipt

Authorized users SHALL be able to prepare a historical stock write-off from an existing draft or cancelled receipt. The source SHALL have no registered payments, invoice, completed or pending delivery, return, applied correction, or debt settlement that would overlap the requested consumption. Preparation SHALL copy stock products and quantities into an editable stock document without changing source receipt data or stock. An existing unfinished document for that source SHALL be reopened instead of creating another active document.

#### Scenario: S01 Prepare from a cancelled receipt
- **GIVEN** an eligible cancelled receipt contains stock products with zero sale prices
- **WHEN** an authorized user starts historical stock write-off
- **THEN** an editable stock document is opened with those products and quantities
- **AND** the receipt remains cancelled and stock is unchanged

#### Scenario: S02 Prepare from a draft receipt
- **GIVEN** an eligible draft receipt has not generated operational or financial effects
- **WHEN** an authorized user starts historical stock write-off
- **THEN** the same preparation workflow is available without requiring payment of the receipt

#### Scenario: S03 Reject an overlapping source
- **WHEN** historical stock write-off is requested for a paid receipt or a source with overlapping payment, delivery, return, correction, or debt history
- **THEN** preparation is rejected with the relevant reason and no stock document is created

### Requirement: Editable stock-only preparation

The preparation document SHALL allow changing products and positive quantities, selecting the historical session and business timestamp, and entering a reason. Authorized users SHALL also be able to change and save the standard scheduled date while the document is a draft. Saving this planned date MUST NOT change the selected historical business timestamp or be rejected as an attempt to rewrite completed stock history. Sale prices, payment methods, revenue and customer debt SHALL NOT be inputs to this operation. Quantities SHALL respect product units and tracking requirements. Saving or cancelling preparation SHALL NOT reserve or consume stock. Cancelling preparation SHALL preserve the source receipt and allow preparation again if it remains eligible.

#### Scenario: S04 Edit the intended consumption
- **WHEN** an authorized user edits products, quantities, the scheduled date or the historical business timestamp through the standard preparation form and saves it
- **THEN** the edited preparation values are retained without a completed-history protection error
- **AND** changing only the scheduled date leaves the historical business timestamp unchanged
- **AND** no stock is reserved or consumed and the source receipt's lines remain unchanged

#### Scenario: S05 Reject invalid preparation data
- **WHEN** application is requested with an empty document, a nonpositive quantity, an incompatible unit, a non-stock product, missing required tracking, or an empty reason
- **THEN** the operation is rejected before any stock consumption

#### Scenario: S06 Discard preparation
- **WHEN** a user cancels an unposted preparation document
- **THEN** no stock, payment or accounting effect remains from preparation
- **AND** the source receipt remains available for a new eligible preparation

### Requirement: Existing historical session and effective date

The user SHALL select an existing closed session of the source receipt's POS and company. The operation SHALL use an explicit stock business timestamp independent of that session's opening and closing interval. The timestamp MAY precede session opening or follow session closure, but MUST be in the past and satisfy stock availability, valuation and period-lock checks at that exact time. Selecting a session SHALL suggest its closing timestamp only when no stock business timestamp has been entered; selecting or changing the linked session MUST preserve an explicitly entered timestamp. Successful completion SHALL give the resulting stock document and all completed movements and movement details that historical timestamp, regardless of the draft's scheduled date. The actual application time and user SHALL remain separately traceable. The operation MUST NOT create or reopen a session, alter its recorded interval, or bypass applicable period locks.

#### Scenario: S07 Select an existing old session
- **GIVEN** an eligible closed session, a supported historical stock situation and a draft whose scheduled date differs from the selected historical business timestamp
- **WHEN** the user selects that session and applies the prepared document
- **THEN** the stock consumption is linked to that session and its document, movements and movement details use the selected historical timestamp independently of the session interval
- **AND** the session remains closed while the actual later application time is retained

#### Scenario: S08 Reject an invalid historical target
- **WHEN** the selected session is not closed, or the stock business timestamp is missing, is not in the past, or violates a period lock
- **THEN** application is rejected without changing the session or stock

#### Scenario: S29 Consume after a receipt recorded outside the linked session interval
- **GIVEN** a linked session closed at 10:39 and a supported receipt added 30 units at 10:52 on the same day
- **WHEN** the user explicitly sets the stock business timestamp to 11:00 and applies a 14-unit consumption
- **THEN** the consumption uses the stock available at 11:00 and completes with that timestamp
- **AND** the linked session retains its original state and closing time
- **AND** selecting 10:39 instead remains invalid because the receipt had not yet occurred

#### Scenario: S30 Preserve an independent timestamp when selecting a session
- **GIVEN** an authorized user entered a supported past stock timestamp before selecting a linked closed session
- **WHEN** the user selects or changes the linked session and saves preparation
- **THEN** the entered stock timestamp is retained, including when it precedes session opening
- **AND** application uses that timestamp rather than replacing it with the session opening or closing time

### Requirement: Stock consumption without a cash sale

Successful application SHALL consume exactly the edited quantities through normal stock operations and make the result visible in historical and current stock information. It SHALL NOT register a POS payment, customer invoice, receivable, sales revenue, debt allocation, or a new cash-session closing operation. Zero sale prices SHALL NOT imply zero stock valuation. The new consumption SHALL use the supported historical valuation. Subsequent outgoing values and related POS costs SHALL be recomputed by an explicit, separately invoked manual operation starting at the earliest selected historical consumption; they SHALL NOT be disguised as sales revenue.

#### Scenario: S09 Complete the intended stock consumption
- **GIVEN** the prepared quantities and historical date satisfy the stock and valuation checks
- **WHEN** the user applies the document
- **THEN** all edited quantities are consumed once with completed, traceable stock movements
- **AND** current quantities and quantities reported after the historical timestamp reflect the consumption

#### Scenario: S10 Preserve sales and payment information
- **WHEN** a historical stock write-off completes successfully
- **THEN** existing sales revenue, customer payments, invoices, debts and the selected session's accounting and cash closing figures are unchanged
- **AND** no new sale or zero-price paid receipt is added to sales reports

#### Scenario: S11 Preserve the source receipt
- **WHEN** historical stock write-off is applied using a cancelled or draft source
- **THEN** its original lines, date, session and POS state remain unchanged
- **AND** its form separately exposes the completed stock write-off and its selected historical session

### Requirement: Supported historical quantities and valuation

Application SHALL validate recorded quantities at the requested business timestamp, the subsequent stock history and current availability. It MUST NOT invent missing opening stock, consume another operation's reserved stock, or silently produce negative quantities through insertion into history. Valuation SHALL follow the standard costing policy for the supported historical case, including FIFO where applicable. Later receipts and today's fallback cost MUST NOT silently substitute for evidence needed at the historical timestamp. The operation SHALL validate that the affected history supports subsequent manual valuation recomputation without rewriting pre-existing posted financial documents. Stock completion SHALL NOT claim that later stored costs have already been recomputed. A canonical product with verified full history consolidation SHALL be evaluated from its unified original movements; absorbed-card links alone MUST NOT cause rejection. Unconverted stock-only consolidations SHALL remain ineligible and identify the required conversion. An unsupported or ambiguous history SHALL be rejected with an actionable reason; using today's date instead SHALL NOT count as successful historical application.

#### Scenario: S12 Reject insufficient historical stock
- **GIVEN** the selected date precedes recorded availability of a required product
- **WHEN** the user applies the stock write-off
- **THEN** application is rejected with the affected product and shortage
- **AND** no opening balance or earlier receipt is fabricated

#### Scenario: S13 Validate the subsequent history
- **GIVEN** stock was sufficient at the selected timestamp but insertion would cause a later shortage, consume current reservations, or prevent the supported subsequent manual valuation recomputation
- **WHEN** the user applies the stock write-off
- **THEN** application is rejected without changing later movements or their posted financial effects

#### Scenario: S14 Reject an unproven valuation path
- **WHEN** the product's historical valuation or downstream impact cannot be determined through the supported standard costing path
- **THEN** the system explains the unsupported condition and leaves the document unposted
- **AND** it does not use zero sale prices, later receipt costs, or current execution time as an unannounced substitute

#### Scenario: H01 Consume a fully unified receipt history
- **GIVEN** full consolidation has combined original August 28 receipts of 20 and 100 units and all other historical checks pass
- **WHEN** the user applies a 31-unit write-off on August 31
- **THEN** the write-off uses the canonical product's combined availability without a generic consolidated-product rejection
- **AND** stock consumption creates no revenue, payment, debt or new session

#### Scenario: H02 Explain an unconverted consolidation
- **GIVEN** the target still has an old stock-only consolidation
- **WHEN** historical consumption is requested
- **THEN** the operation identifies the source group requiring full history conversion and remains unposted

#### Scenario: H03 Retain quantity safeguards after consolidation
- **GIVEN** a fully consolidated product has insufficient historical stock or would develop a later shortage
- **WHEN** historical consumption is requested
- **THEN** it is rejected under the same quantity rules as an ordinary product

### Requirement: Atomic and repeatable application

Application SHALL be atomic, revalidate current facts and prevent duplicate consumption for a source receipt. Repeating preparation or application SHALL return the existing applicable document or completed result. An error or unresolved partial delivery SHALL roll back the entire application. Concurrent historical application or ordinary processing of the source SHALL NOT create two consumptions. Changes to the source or relevant stock facts since preparation SHALL be revalidated before any effects are committed.

#### Scenario: S15 Retry preparation or application
- **WHEN** preparation is requested again for a source with an active document or application is repeated after success
- **THEN** the existing document or completed result is returned
- **AND** no additional stock document or consumption is created

#### Scenario: S16 Roll back incomplete application
- **WHEN** one required stock operation fails or cannot complete all quantities after another operation has started
- **THEN** the entire attempt is rolled back without completed partial consumption or a successful result

#### Scenario: S17 Protect against concurrent or stale processing
- **WHEN** another request changes the source, consumes relevant stock, starts ordinary payment or delivery, or applies the same historical document concurrently
- **THEN** at most one incompatible processing path succeeds
- **AND** an invalidated attempt must refresh or correct its data before application

### Requirement: Traceable and protected history

The operation SHALL retain the source receipt, target session, edited stock lines, reason, author, business timestamp, actual application time and resulting stock document. Users with the required access SHALL navigate this history from both the receipt and target session. Completed historical consumption SHALL NOT be silently edited, deleted, copied as another historical application, or reverted to preparation. Reversing completed historical consumption is outside this capability and SHALL NOT be offered as a draft reset. A source already consumed by this mechanism SHALL NOT subsequently generate an ordinary sale or another historical consumption of the same stock.

#### Scenario: S18 Inspect the recorded result
- **WHEN** an authorized user opens the source receipt or selected historical session
- **THEN** the user can open the stock write-off and distinguish its historical business timestamp from the actual application time

#### Scenario: S19 Protect completed history
- **WHEN** an edit, including a direct change to a completed movement date, deletion, copy, direct import or draft-reset request attempts to rewrite a completed historical consumption
- **THEN** the request is rejected without changing the recorded stock effects

#### Scenario: S20 Prevent reuse as an ordinary cash sale
- **GIVEN** a source receipt has a completed historical stock write-off
- **WHEN** ordinary payment, delivery or another historical consumption is attempted from that source
- **THEN** the duplicate processing is rejected and the existing result is retained

### Requirement: Permission and company boundaries

Preparing, changing and applying historical stock write-offs SHALL require a dedicated permission in addition to access to the source and relevant stock operations. The same checks SHALL apply to interface actions, imports and direct requests. Source receipt, target session, stock locations, products and tracked stock SHALL be compatible with one authorized company and the same POS. Read access SHALL respect existing company and document access policies without granting unrestricted accounting access.

#### Scenario: S21 Reject an unauthorized direct request
- **WHEN** a user without the dedicated permission attempts preparation, editing or application through any supported entry point
- **THEN** the request is denied without stock or financial changes

#### Scenario: S22 Reject incompatible company or POS data
- **WHEN** a request mixes incompatible source, session, location or product data or accesses an unauthorized company
- **THEN** the request is rejected without modifying either company's records

### Requirement: Project installation and ordinary workflow continuity

The capability SHALL be installed with the main Tire application. Installation or upgrade SHALL NOT automatically process existing receipts, create sessions, or change historical stock. Ordinary POS sales, corrections, customer debt settlement and stock operations SHALL retain their existing behavior when this capability is not invoked. Additional navigation SHALL NOT replace standard order or session lists, searches or their existing columns.

#### Scenario: S23 Install without processing history
- **WHEN** the main Tire application is installed or upgraded with this capability available
- **THEN** the historical stock write-off feature is installed
- **AND** existing receipts, sessions, stock and financial documents are not processed by installation alone

#### Scenario: S24 Preserve ordinary workflows
- **WHEN** a user processes an ordinary order or stock operation without a historical write-off
- **THEN** existing sales, correction, debt and stock behavior is unchanged
- **AND** ordinary order and session navigation retains its standard views

### Requirement: Manual recomputation from the earliest historical consumption

After one or more historical consumptions, an authorized user SHALL be able to
invoke the existing cost-recomputation tool in a dedicated historical mode.
Selected completed historical documents SHALL determine the earliest inclusive
business timestamp and affected products within one company. For fully consolidated products, the system SHALL expand the inclusive start when necessary to cover the earliest affected outgoing movement identified by their applied consolidation history, including earlier affected issues before the selected consumption. Preview SHALL include
all subsequent affected outgoing movements through the preview cutoff, including
nonzero values and operations outside the initially selected receipts, together
with their supported completed POS costs. Applying a reviewed plan SHALL update
stock values first and POS costs second, atomically, using standard historical FIFO
calculations and preserving before/after audit evidence. Revenue, payments, debts,
quantities and posted accounting entries MUST remain unchanged by recomputation.
Ordinary cost-recomputation and zero-stock-value-repair modes SHALL remain unchanged.
No automatic invocation or separate pending-recomputation marker SHALL be added.

#### Scenario: S25 Recompute from the earliest of multiple transfers
- **GIVEN** several completed historical consumptions affect a product at different dates
- **WHEN** the user selects them and manually previews historical recomputation
- **THEN** all affected subsequent stock issues are evaluated from the earliest selected date
- **AND** existing nonzero values and related eligible POS costs are included, not only the selected source receipts

#### Scenario: S26 Apply stock costs before POS costs
- **GIVEN** an earlier inserted consumption changes a later issue's FIFO cost from 200 to 300
- **WHEN** the user manually applies the reviewed historical recomputation
- **THEN** that issue's stored value becomes 300 before its linked eligible POS costs are recomputed
- **AND** the original and new values remain auditable without changing revenue, payments or quantities

#### Scenario: S27 Preserve manual control without pending markers
- **WHEN** a historical consumption completes
- **THEN** the user may separately start cost recomputation
- **AND** no automatic downstream recomputation or additional pending marker is created

#### Scenario: S28 Reject stale or unsupported manual recomputation
- **WHEN** relevant history changes after preview or cannot be recomputed under the supported costing and financial constraints
- **THEN** applying the proposed plan is rejected without partial cost changes
- **AND** the user receives a reason and must review current data

#### Scenario: H04 Include earlier costs affected by a merge
- **GIVEN** full consolidation affects an issue dated before the selected historical consumption
- **WHEN** the user previews manual historical recomputation
- **THEN** the displayed start includes that earlier issue and all subsequent affected issues through the cutoff
- **AND** both merge and consumption reasons for the expanded range are visible
