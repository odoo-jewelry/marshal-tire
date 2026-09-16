# POS Order Correction Specification

> [!abstract] Исправление товаров и оплат кассовой продажи
> Позволяет исправлять завершённую продажу с сохранением исходного чека, истории изменений и связанных складских и бухгалтерских операций.
>
> **Использование:**
>
> В административном меню «Торговая точка → Заказы → Заказы» уполномоченному сотруднику доступна кнопка «Исправить чек». В форме заказа добавлена вкладка «Текущая продажа» с действующими товарами, количеством, ценой, скидкой, налогами, суммой строки, текущим итогом и распределением оплат. Прежние вкладки товаров и оплат названы «Исходные товары» и «Исходные оплаты». Кнопка «Исправления» и вкладка «История исправлений» показывают ревизии, причину, состояние, смену, автора, время и связанные документы. Уведомления показывают ожидание складской обработки и закрытия смены. Существующие поля не удалены.
>
> В форме подготовки исправления доступны товары, количество, цена, скидка, партии или серийные номера, способы оплаты и суммы; налоги рассчитываются по стандартным правилам. Поля «Причина» и «Смена исправления» задают основание и открытую смену той же кассы. Покупатель, компания и исходный заказ доступны для просмотра. Действие «Применить исправление» сохраняет результат, а отмена подготовки оставляет продажу без изменений. Применённая ревизия содержит предыдущие и итоговые значения, автора, время и ссылку на созданный документ.
>
> Исправлять можно завершённые продажи открытых и закрытых смен без счетов, обычных возвратов и последующего погашения долга. Изменение применяется в открытой смене той же кассы. Неоднозначная история, неподходящие партии, чужая компания или несогласованная сумма оплат препятствуют применению. Изменение регистрации оплаты не выполняет операции банковского терминала.
>
> Например, замена товара A на B возвращает только изменяемое количество A и отражает выдачу B; исправление одной цены не перемещает товар. Для продажи на 100 можно заменить наличную оплату банковской или изменить распределение 70/30 на 20/80. Исправление продажи в долг сохраняет одну задолженность исходного заказа, а уменьшение ещё не доставленного количества сокращает оставшийся спрос.
>
> После закрытия связанных смен поздний счёт и обычный возврат используют текущую продажу. Существующий экран возврата кассы показывает действующие строки, в том числе из нескольких исправлений, и не позволяет вернуть уже заменённое или избыточное количество. Новый счёт, обычный возврат или погашение долга прекращают доступность дальнейшего исправления. Ранее применённый результат восстанавливают новой допустимой ревизией, сохраняя всю историю.
^feature-card

## Purpose

Allow authorized users to correct products and recorded payment methods on completed POS sales from the administrative order form while preserving original documents and traceable stock and accounting effects.

## Requirements

### Requirement: Correction eligibility

The system SHALL offer correction for completed sales from open or closed sessions without invoices, ordinary customer returns, or subsequent debt settlements. Eligibility SHALL cover the entire correction history and SHALL be checked both when editing starts and when changes are applied. Correction-generated offsets SHALL NOT count as ordinary customer returns. Draft and cancelled sales, return documents, and ambiguous accounting or stock histories SHALL be rejected with an explanation.

#### Scenario: S01 Eligible open-session sale
- **WHEN** an authorized user starts correction of a completed eligible sale in an open session
- **THEN** the administrative order form offers editable correction data initialized from the current effective sale

#### Scenario: S02 Eligible closed-session sale
- **WHEN** an authorized user starts correction of an eligible sale from a closed session
- **THEN** correction data is available without reopening that session

#### Scenario: S03 Excluded document history
- **WHEN** correction is requested for a sale with an invoice, an ordinary return, or a subsequent debt settlement, including such history on a related correction
- **THEN** the request is rejected with the relevant reason and no correction is applied

#### Scenario: S04 Invalid source document
- **WHEN** correction is requested for a draft sale, a cancelled sale, a return document, or a sale with ambiguous required accounting or stock links
- **THEN** the request is rejected without guessing missing links

### Requirement: Isolated correction editing

Correction mode SHALL expose products, quantities, unit prices, discounts, and payment distribution from the current effective sale. Customer, company, currency, original session and original date SHALL remain unchanged. Taxes and rounding SHALL use standard rules. Saving editing data alone SHALL NOT apply a correction. Applying SHALL require a nonempty reason and an explicit save-correction action; discarding unconfirmed editing SHALL have no operational effects.

#### Scenario: S05 Prepare and discard changes
- **WHEN** a user edits correction data and then discards it
- **THEN** the original sale, effective sale, inventory, payments and accounting remain unchanged

#### Scenario: S06 Apply without a reason
- **WHEN** a user applies a changed correction without a reason
- **THEN** the system requests a reason and applies nothing

#### Scenario: S07 No effective changes
- **WHEN** a user applies correction data identical to the current effective sale
- **THEN** the system reports that no changes are needed and creates no operational correction documents

#### Scenario: S08 Invalid correction values
- **WHEN** correction data changes protected sale identity, contains invalid quantities or discounts, lacks required lot identification, or uses an unavailable product or payment method
- **THEN** the system rejects the data with an explanation before applying any effects

### Requirement: Corrected product effects

Applying a product correction SHALL update the effective sale and create traceable offsets and replacement effects only for changed items. Unchanged items SHALL NOT be returned and sold again. Completed stock movements SHALL be preserved. Changes SHALL respect standard units, taxes, rounding, lot or serial identification and the actual delivery state. Price-only changes SHALL NOT move stock. Unexpected failure to complete an immediately required movement SHALL prevent successful application.

#### Scenario: S09 Replace a delivered product
- **GIVEN** a sale records one delivered unit of A while the intended sale is one unit of B
- **WHEN** the user applies that replacement with valid stock identification and payment distribution
- **THEN** the effective sale contains B and the correction restores the recorded unit of A and records delivery of B with links to the source effects

#### Scenario: S10 Preserve unchanged items
- **GIVEN** a sale contains A and C
- **WHEN** only A is replaced by B
- **THEN** no correction movement is created for C

#### Scenario: S11 Change quantity
- **GIVEN** a sale records three units of A and has no ordinary returns
- **WHEN** its effective quantity is corrected to two with matching payment distribution
- **THEN** the stock correction restores exactly one unit of A

#### Scenario: S12 Change price without moving stock
- **WHEN** only a product price or discount is corrected with matching payment distribution
- **THEN** the effective price, taxes and sale total follow standard calculations without additional stock movements

#### Scenario: S13 Stock is updated at session closure
- **GIVEN** the source sale has not yet moved stock because its session updates stock at closure
- **WHEN** a product correction is applied and that session subsequently closes
- **THEN** the final stock effect equals the corrected sale without a duplicate delivery or a return of goods never delivered

#### Scenario: S14 Preserve tracked stock identity
- **GIVEN** the changed product requires lot or serial tracking
- **WHEN** a valid correction is applied
- **THEN** the offset identifies the original tracked movement and the replacement identifies the intended tracked stock without selecting an arbitrary source movement

#### Scenario: S41 Correct partially delivered demand
- **GIVEN** three units were sold for later delivery and one unit has already been delivered
- **WHEN** the sale is corrected to two units with matching payments
- **THEN** the delivered unit remains delivered and the remaining demand becomes one unit without returning undelivered stock

#### Scenario: S43 Product replacement after a price correction
- **GIVEN** the price of delivered A was corrected without a stock movement
- **WHEN** a later correction replaces A with B
- **THEN** A is restored against its actual original delivery and B is delivered without inventing a stock source for the price-only correction

### Requirement: Corrected payment registration

The system SHALL allow changing recorded payment methods and split-payment amounts. The effective payment distribution SHALL match the corrected sale total under standard rounding and change rules. Payment corrections SHALL record differences from the previous effective distribution. They SHALL NOT invoke a terminal, bank, or fiscal-device operation or present a registration change as proof of a new external payment. A request requiring such an external operation SHALL be rejected by this workflow.

#### Scenario: S15 Replace cash with bank registration
- **GIVEN** an eligible sale of 100 is recorded as cash but was actually paid by bank
- **WHEN** the user corrects registration to bank 100
- **THEN** the effective distribution is cash zero and bank 100, with a traceable cash decrease of 100 and bank increase of 100 and no stock correction

#### Scenario: S16 Correct a split payment
- **GIVEN** an eligible sale of 100 is recorded as cash 70 and bank 30
- **WHEN** the distribution is corrected to cash 20 and bank 80
- **THEN** the recorded correction is cash minus 50 and bank plus 50

#### Scenario: S17 Reject an unmatched total
- **WHEN** corrected items total 120 but effective payments cover only 100 without valid standard rounding or change treatment
- **THEN** saving is rejected and the user sees the remaining amount to allocate

#### Scenario: S18 Preserve external transaction evidence
- **WHEN** a proposed correction requires changing or reversing an actual terminal transaction through the provider
- **THEN** this workflow refuses that operation without changing provider evidence or sending an external request

#### Scenario: S42 Preserve tax rounding and cash change
- **GIVEN** the effective sale includes tax-inclusive prices, cash rounding or recorded change
- **WHEN** its products or payment distribution are corrected
- **THEN** the effective totals follow the same standard calculation rules and the correction accounts only for the difference without duplicating original change

### Requirement: Current-session accounting

Applied corrections SHALL belong to an open session of the same POS and company and SHALL use the correction date. Closed source sessions and their posted accounting SHALL remain unchanged. Application SHALL expose whether related stock or accounting effects await standard session closure; it SHALL NOT claim deferred accounting is posted. Source-period reports SHALL retain the original operation and correction-period reports SHALL include the difference exactly once.

#### Scenario: S19 Correct a closed-session payment
- **GIVEN** a source session is closed and the same POS has an open session
- **WHEN** a payment correction is applied and the current session closes
- **THEN** that session posts the payment-method difference while source-session accounting remains unchanged

#### Scenario: S20 No open target session
- **WHEN** a correction is saved without an open session of the same POS and company
- **THEN** the system explains that a session must be opened and applies no operational effects

#### Scenario: S21 Pending accounting is visible
- **WHEN** a correction has been applied in a session that has not closed
- **THEN** the source form shows the corrected sale and indicates that correction accounting awaits session closure

#### Scenario: S22 Reports include the difference once
- **GIVEN** a sale of A for 100 in an earlier period is corrected to B for 120 in the current period
- **WHEN** sales and accounting reports are generated after correction-session closure
- **THEN** the earlier period retains A for 100 and the current period contains the offset of A for 100 and B for 120, yielding a combined net sale of B for 120

### Requirement: Customer-account continuity

An eligible customer-account sale without subsequent settlement SHALL remain correctable. Its effective debt SHALL be derived from posted accounting for the source and applied corrections, without duplicate collection targets. Settlement SHALL be unavailable while any related correction accounting is pending. Correction credits SHALL offset only the identified source sale; they SHALL NOT settle another sale of the same customer. Posted internal correction offsets SHALL NOT count as subsequent customer payments for eligibility.

#### Scenario: S23 Replace unsettled customer-account registration
- **GIVEN** an identified eligible closed-session sale of 100 is recorded entirely on the customer account and has no subsequent settlement
- **WHEN** registration is corrected to cash 100 and the correction session closes
- **THEN** its outstanding debt becomes zero through traceable accounting offsets

#### Scenario: S24 Correct a sale amount on the customer account
- **GIVEN** an eligible customer-account sale has debt 100 and another sale of the same customer has debt 80
- **WHEN** the first sale and its customer-account distribution are corrected to 120 and the correction session closes
- **THEN** the first sale has one effective collection target of 120 and the other sale still has debt 80

#### Scenario: S25 Settlement while correction is pending
- **WHEN** settlement is requested for a sale with applied correction accounting still awaiting closure
- **THEN** settlement is rejected until all related accounting is posted

#### Scenario: S44 Replace cash registration with customer account
- **GIVEN** an identified eligible sale of 100 was recorded in cash and has no subsequent settlement
- **WHEN** payment registration is corrected to customer account 100 and the correction session closes
- **THEN** the source sale becomes one collection target with outstanding debt 100, without a duplicate target for the correction document

### Requirement: Atomic and repeatable application

Correction application SHALL be atomic and idempotent. A repeated request for an applied correction SHALL return that same result. Concurrent editing, session closure, invoicing, returns or settlement SHALL NOT allow application against stale facts. Batch requests SHALL preserve company boundaries and SHALL NOT leave partial effects if any requested correction fails.

#### Scenario: S26 Failure during application
- **WHEN** a required stock or payment operation fails after other correction effects have started
- **THEN** all effects of that application are rolled back and no successful revision is recorded

#### Scenario: S27 Retry the same application
- **WHEN** the same save-correction request is submitted again after successful application
- **THEN** the original result is returned without duplicate documents, payments or movements

#### Scenario: S28 Concurrent or stale correction
- **GIVEN** correction data was prepared before another correction or eligibility-changing operation committed
- **WHEN** the stale data is applied
- **THEN** the application is rejected and the user must reload current data

#### Scenario: S29 Mixed batch failure
- **WHEN** a batch applies several corrections and one is invalid or belongs to an unauthorized company
- **THEN** no correction in that batch is partially applied

### Requirement: Traceable revision history

The source order SHALL expose the latest applied effective sale as its default working view. The unchanged original document and all correction revisions SHALL be available through change history, with original values clearly distinguished from current values. Every applied correction SHALL retain its reason, author, time, previous and resulting values, and links to generated documents. Repeated corrections SHALL use the latest effective sale. Saving or cancelling a draft SHALL NOT change that effective sale. Applied history and generated documents SHALL NOT be silently edited, deleted or duplicated; an applied correction SHALL be undone only by a new eligible correction. Correcting an error from an earlier applied revision SHALL start from the latest effective sale and SHALL NOT rewrite that earlier revision or automatically replay intervening revisions.

#### Scenario: S30 Inspect correction history
- **WHEN** a user opens the history of a corrected source order
- **THEN** the original receipt and every correction revision are accessible, with the correction state, reason, author, application time and links to operational documents
- **AND** an applied revision offers a readable comparison of its previous and resulting values while drafts and cancelled preparations remain distinguishable from applied changes

#### Scenario: S31 Correct the latest result
- **GIVEN** a sale originally containing A has already been corrected to B
- **WHEN** another correction replaces B with C
- **THEN** only the effective B is offset and the resulting effective sale contains C

#### Scenario: S32 Protect applied history
- **WHEN** editing, deletion, cancellation or duplication attempts to rewrite or reapply an applied correction or its generated records outside the correction workflow
- **THEN** the request is rejected or, for an ordinary source-order copy, correction ownership is cleared without generating correction effects

#### Scenario: S40 Undo through another correction
- **GIVEN** an eligible sale of A was corrected to B
- **WHEN** the user applies a new correction restoring A and the original payment distribution
- **THEN** the effective result is restored through a new traceable revision while the previous revision and its documents remain intact

#### Scenario: S45 Prepare a third correction
- **GIVEN** an eligible sale has two applied corrections
- **WHEN** the user starts another correction from its source order
- **THEN** editable products and payment distribution are initialized from the second applied result and applying the changes records a new revision

#### Scenario: S46 Correct an earlier mistake after later changes
- **GIVEN** the second applied correction set an incorrect quantity and the third applied correction changed the payment distribution
- **WHEN** the user prepares a fourth correction from the current sale, changes the quantity and adjusts payments as required by the resulting total
- **THEN** the fourth correction changes the latest effective sale while preserving unchanged current values and all three prior revisions

#### Scenario: S47 Continue an unapplied correction
- **GIVEN** the source order has an existing draft correction
- **WHEN** the user starts correction again
- **THEN** that draft is reopened without discarding its edits or creating a second preparation, and existing stale-data validation still applies on application

### Requirement: Access and standard workflow continuity

Correction SHALL require a dedicated permission in addition to access to affected source and operational records. The same validation SHALL apply to direct requests and imports. Ordinary sales SHALL retain standard behavior. Later invoicing and ordinary returns of a corrected sale SHALL use its effective products and payments exactly once and preserve correction history; once such a document exists, further correction SHALL be unavailable. Pending correction posting SHALL prevent these later actions until the effective accounting is complete.

#### Scenario: S33 Unauthorized direct request
- **WHEN** a user without correction permission invokes correction directly or imports protected applied state
- **THEN** the operation is rejected without privilege escalation

#### Scenario: S34 Company isolation
- **WHEN** a user attempts to combine a source sale with a session, product, payment method or stock source incompatible with its company
- **THEN** the operation is rejected without modifying either company's records

#### Scenario: S35 Ordinary POS behavior
- **WHEN** a sale is processed without using correction
- **THEN** standard payment, delivery, invoicing, return, session closure and debt settlement behavior are preserved

#### Scenario: S36 Later invoice
- **GIVEN** a sale has completed correction accounting
- **WHEN** a user subsequently invoices it
- **THEN** the invoice uses the effective sale and payments exactly once without invoicing offset items, and further correction becomes unavailable

#### Scenario: S37 Later ordinary return
- **GIVEN** a sale has completed correction accounting
- **WHEN** a user subsequently starts an ordinary return
- **THEN** only effective unreturned quantities can be returned with links to their stock sources, and the ordinary return makes further correction unavailable

#### Scenario: S38 Later action before correction closure
- **WHEN** invoicing or an ordinary return is requested while correction accounting is still pending
- **THEN** the system explains that the related correction session must close first and creates no invoice or ordinary return

#### Scenario: S39 Repeated installation or upgrade
- **WHEN** the module is installed or upgraded on a database containing historical sales, or the upgrade is repeated
- **THEN** no historical sale is rewritten and no correction or accounting offset is generated by installation alone

### Requirement: Current receipt as the primary administrative view

The administrative source-order form SHALL present products and recorded payments on separate ordinary Products and Payments tabs. For a source with applied corrections these tabs SHALL show the latest effective products, payment distribution and sale total, with effective data read-only outside correction preparation. Original values SHALL be accessed through history rather than competing Original Products, Original Payments or Current Sale tabs. For an order without applied corrections, standard products, payments, totals and editing behavior SHALL remain available. Empty effective products or payments SHALL NOT cause fallback to original values. The current payment distribution SHALL represent recorded sale allocation, not a new external transaction or subsequent debt settlement.

#### Scenario: S48 Open the current corrected receipt
- **GIVEN** a receipt originally totalled 100 and its latest applied correction changed it to 120
- **WHEN** the user opens the source order
- **THEN** the default Products tab shows the effective items and total 120, and the Payments tab shows the effective allocation rather than only the correction difference
- **AND** the original total 100 is available through history without a competing original tab in the working receipt

#### Scenario: S49 Find current payments independently of products
- **GIVEN** a receipt originally recorded cash 100 and an applied correction changed registration to bank 100
- **WHEN** the user opens its Payments tab
- **THEN** the effective distribution is bank 100 with no nonzero cash allocation, and the sale total is 100
- **AND** the original cash registration and its offset remain accessible through history

#### Scenario: S50 Keep preparation separate from the current receipt
- **GIVEN** a source order has an applied correction and a later draft with different products or payments
- **WHEN** the user saves or cancels that draft and opens the source order
- **THEN** the working tabs still show the last applied result, and history identifies the preparation by its actual state

#### Scenario: S51 Preserve orders without applied corrections
- **WHEN** a user opens an ordinary order, including a draft, a cancelled order, an ordinary return, or an order with only draft or cancelled correction preparations
- **THEN** standard products, payments, totals, signs and editing permissions are preserved without misleading original/current tab duplication
- **AND** correction eligibility remains unchanged

#### Scenario: S62 Display an empty effective sale
- **GIVEN** an applied correction removed all sale items and effective payment allocation
- **WHEN** the user opens the source order
- **THEN** the working Products and Payments tabs show an empty effective sale and zero total without restoring original items or amounts

### Requirement: Navigation returns to the effective receipt

Successful correction application SHALL open the source order with its latest effective sale. Retrying an applied correction SHALL open the same source order without generating additional effects; if newer revisions exist, the working form SHALL show the newest applied state. Generated difference documents SHALL remain separately accessible from history and correction details, SHALL be visibly identified as correction operations, and SHALL offer navigation to the effective source receipt. Opening a difference document SHALL continue to show that document's own operational values.

#### Scenario: S52 Apply and return to the receipt
- **WHEN** a user successfully applies a correction
- **THEN** the returned form is the source receipt with updated effective products, payments and total rather than the generated difference document

#### Scenario: S53 Retry an older applied correction
- **GIVEN** an applied correction has already been followed by a newer applied correction
- **WHEN** application of the older correction is retried
- **THEN** no documents or movements are created and the source receipt opens with the newest applied result

#### Scenario: S54 Inspect a difference and return
- **WHEN** a user opens a generated document from correction history
- **THEN** the form clearly identifies it as a correction difference, shows its own items, payments and total, and offers return to the effective source receipt

### Requirement: Readable original and revision details

Change history SHALL provide read-only access to the original receipt and human-readable Before and After views of each applied revision's recorded products, quantities, unit prices, discounts, taxes, tracked identifiers, product attributes where recorded, and payment distribution. Reading these values SHALL NOT require interpreting technical serialized data. Earlier revision details SHALL remain tied to the recorded values for that revision after later corrections. Missing historical values SHALL be identified as unavailable rather than inferred from the current sale or recalculated under current tax settings. Viewing history SHALL respect existing record access and company restrictions and SHALL NOT modify documents or grant correction permission.

#### Scenario: S55 Read the original receipt from history
- **GIVEN** a receipt has several applied corrections
- **WHEN** the user opens its original version from history
- **THEN** the original items, payment records, total, date and session are shown read-only and clearly labelled as original values

#### Scenario: S56 Compare an intermediate revision
- **GIVEN** a receipt has three applied corrections
- **WHEN** the user opens the second revision
- **THEN** readable Before and After values describe the second revision's own change, including its product and payment values, rather than substituting the third revision's result

#### Scenario: S57 Display incomplete historical details honestly
- **GIVEN** an existing revision lacks a recorded detail or references a deleted or inaccessible descriptive record
- **WHEN** an authorized user reads its comparison
- **THEN** the available recorded values remain readable and the unavailable detail is identified without inventing historical values or exposing restricted record contents

#### Scenario: S58 Restrict history navigation and display
- **WHEN** a user invokes a history, original-receipt or return-to-receipt action for records outside their access or active companies
- **THEN** protected contents are not exposed through the action or its rendered comparison, and no additional editing or correction rights are granted

### Requirement: Presentation continuity during correction interface upgrades

The interface change SHALL preserve pending stock and session-closure notices, standard correction validation and permissions, and operational accounting, payment, stock and debt behavior. Installation or upgrade SHALL NOT rewrite original orders or recorded revisions, create operational documents, or require fabricated historical snapshots. Standard order list and search selection, receipt number, customer, total and status columns, and optional debt-column behavior SHALL remain unchanged.

#### Scenario: S59 Preserve pending processing notices
- **GIVEN** a corrected sale awaits stock processing or correction-session closure
- **WHEN** the user opens the effective receipt
- **THEN** the applicable pending notice remains visible and the current presentation does not imply that deferred operations have completed

#### Scenario: S60 Upgrade existing correction history
- **WHEN** the module is upgraded on a database containing original orders, applied revisions and draft preparations
- **THEN** existing records become accessible through the updated presentation without rewriting history, changing draft contents or generating new operational effects

#### Scenario: S61 Preserve the standard orders list
- **WHEN** the user opens the standard Orders action after installation or upgrade
- **THEN** its standard list and search remain selected, receipt number, customer, total and status retain their established arrangement, and debt columns retain their optional behavior
