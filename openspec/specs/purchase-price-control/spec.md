# Purchase Price Control Specification

> [!abstract] Контроль закупочных и продажных цен
> Позволяет закупщикам видеть расчётные показатели цены и явно сохранять закупочную и продажную цены товара при подтверждении заказа.
>
> **Использование:**
>
> В `Purchase > Configuration > Settings` добавлен блок Price Control с полями наценки по умолчанию и шага округления продажной цены для каждой компании. Стандартные поля настроек не изменялись и не удалялись.
>
> В форме запроса коммерческого предложения и заказа на закупку в товарных строках добавлены текущая справочная закупочная цена, текущая продажная цена, наценка, эффективная закупочная цена, плановая продажная цена и флажок `Save Prices`. При подтверждении заказа система сохраняет рассчитанные значения только для отмеченных товарных строк; секции, подсекции, заметки и авансовые строки не участвуют.
>
> Основные сценарии: сравнение текущих и плановых цен до подтверждения; применение company-specific наценки и округления; сохранение цен выбранных строк при обычном подтверждении или переходе в To Approve; повторное применение после возврата заказа в draft. Неотмеченные строки сохраняют стандартное поведение Odoo, отмена заказа не откатывает уже сохранённые цены, а дубликат заказа очищает флажки.
^feature-card

## Purpose

Provide purchase users with a company-aware reference purchase price, markup visibility, and an explicit way to update reference purchase and sales prices when confirming a purchase order.

## Requirements

### Requirement: Company price-control configuration

The system SHALL provide each company with a default markup percentage and a positive sales-price rounding step in the Purchase settings. The initial rounding step SHALL be `0.01`, and the initial default markup SHALL be `0%`.

#### Scenario: Configure price control for one company

- **WHEN** an administrator saves a default markup of `25%` and a rounding step of `10` for a company
- **THEN** purchase price calculations for that company use those values
- **AND** another company's configuration remains unchanged

#### Scenario: Reject a non-positive rounding step

- **WHEN** an administrator attempts to save a rounding step equal to or below zero
- **THEN** the system rejects the configuration with a validation message

### Requirement: Independent reference purchase price

The system SHALL maintain `last_purchase_price` for each product variant and company in the company's currency and the product's base unit of measure. This value SHALL be independent of inventory valuation cost.

#### Scenario: Different reference prices by company

- **GIVEN** the same product is available in two companies
- **WHEN** its reference purchase price is updated in one company
- **THEN** the reference purchase price in the other company remains unchanged

#### Scenario: Inventory valuation remains unchanged

- **WHEN** a reference purchase price is saved for a product using Standard Price, AVCO, or FIFO
- **THEN** the product inventory valuation cost and lot valuation costs remain unchanged

### Requirement: Purchase-line price-control information
For every eligible product line, regardless of purchase-order state, the system SHALL display the current-price snapshot, current markup percentage, effective purchase price, rounded planned sales price, and the applicable manual price action. Section, subsection, note, and down-payment lines SHALL NOT participate in price control.

#### Scenario: Display markup based on a saved reference price
- **GIVEN** a product has a reference purchase price of `100` and a current sales price of `150`
- **WHEN** the user invokes Fill Current Prices for its purchase-order line
- **THEN** the stored current markup is displayed as `50%`

#### Scenario: Use the default markup without a reference price
- **GIVEN** a product has no positive reference purchase price and the company default markup is `30%`
- **WHEN** the user invokes Fill Current Prices for its purchase-order line
- **THEN** the stored current markup is `30%`
- **AND** the planned sales price is calculated using `30%`

#### Scenario: Display initialized price-control information in any state
- **GIVEN** an eligible line has an initialized snapshot
- **WHEN** its purchase order is draft, sent, awaiting approval, confirmed, locked, cancelled, or reset to draft
- **THEN** the line displays its snapshot and calculated price-control values
- **AND** manual actions are governed by price discrepancies rather than the order state

#### Scenario: Ignore non-product lines
- **WHEN** a purchase order contains a section, subsection, note, or down-payment line
- **THEN** that line has no current-price snapshot actions
- **AND** it cannot update any product price

### Requirement: Effective purchase price calculation

The effective purchase price SHALL represent one product base unit, including the selected purchase taxes and the line discount. It SHALL be converted from the purchase order currency to the company currency using the order date and company exchange-rate rules.

#### Scenario: Apply discount and taxes

- **GIVEN** a line unit price of `100`, a line discount of `10%`, and purchase taxes totaling `20%`
- **WHEN** the effective purchase price is calculated
- **THEN** it equals `108` before currency and unit-of-measure conversion

#### Scenario: Convert purchase unit and currency

- **GIVEN** the purchase line uses a purchase unit different from the product base unit and a currency different from the company currency
- **WHEN** the effective purchase price is calculated
- **THEN** the displayed value is the tax-included discounted price per product base unit in company currency

#### Scenario: Recalculate after commercial terms change

- **WHEN** the product, unit price, discount, taxes, purchase unit, order currency, company, or order date changes before confirmation
- **THEN** the effective purchase price and dependent planned sales price reflect the changed terms

### Requirement: Planned sales price and upward rounding
For an initialized eligible line, the system SHALL allow the user to enter a planned sales price directly. The system SHALL preserve the exact manually entered value without changing the line markup or any other calculated value. Subsequent changes to the effective-purchase-price basis SHALL NOT change a manually entered planned sales price. Invoking Fill Current Prices SHALL clear the manual value and restore the automatically calculated and upward-rounded planned sales price. An uninitialized line SHALL NOT accept a usable manual planned sales price or offer a price-update action.

#### Scenario: Round upward to a whole-price step
- **GIVEN** an initialized line has an unrounded planned sales price of `121` and a rounding step of `10`
- **WHEN** the planned sales price is calculated
- **THEN** it equals `130`

#### Scenario: Preserve an exact multiple
- **GIVEN** an initialized line has an unrounded planned sales price of `120` and a rounding step of `10`
- **WHEN** the planned sales price is calculated
- **THEN** it remains `120`

#### Scenario: Round upward to a fractional step
- **GIVEN** an initialized line has an unrounded planned sales price of `12.341` and a rounding step of `0.10`
- **WHEN** the planned sales price is calculated
- **THEN** it equals `12.40`

#### Scenario: Enter a planned sales price directly
- **GIVEN** an initialized line has an effective purchase price of `100`
- **AND** the configured rounding step is `0.01`
- **WHEN** the user enters a planned sales price of `12`
- **THEN** the planned sales price remains exactly `12`
- **AND** the line markup remains unchanged
- **AND** no product price is changed by editing the line

#### Scenario: Preserve a manual price after the purchase-price basis changes
- **GIVEN** a user entered a planned sales price of `12`
- **WHEN** the unit price, discount, taxes, purchase unit, currency, company, or order date changes
- **THEN** the planned sales price remains exactly `12`
- **AND** the line markup remains unchanged by the manual sales-price entry

#### Scenario: Restore automatic calculation explicitly
- **GIVEN** a line has a manually entered planned sales price
- **WHEN** the user invokes Fill Current Prices
- **THEN** the manual planned sales price is cleared
- **AND** the planned sales price is calculated from the refreshed markup and effective purchase price
- **AND** the configured upward rounding rule is applied

#### Scenario: Keep automatic calculation when manual entry is not used
- **GIVEN** an initialized eligible line has not received a manual planned sales price
- **WHEN** its effective-purchase-price basis changes
- **THEN** the system continues to calculate and round the planned sales price from the existing line markup

#### Scenario: Do not calculate from an absent snapshot
- **GIVEN** an eligible line has not been filled with current prices
- **WHEN** the user edits its commercial terms
- **THEN** the line remains uninitialized
- **AND** it does not offer a usable manual planned sales price or a product-price update

### Requirement: Explicit price saving on confirmation
The system SHALL NOT save reference purchase prices, sales prices, or standard costs as a side effect of confirming or approving a purchase order. Product prices and standard cost SHALL change through price control only when a user explicitly invokes a line-level or order-level price update action.

#### Scenario: Save an explicitly selected line
- **GIVEN** an initialized Standard Price line has a price or cost discrepancy
- **WHEN** the user invokes its Update action
- **THEN** reference purchase price, sales price, and standard cost are updated from the line's fixed calculated values
- **AND** no purchase-order lifecycle transition is required

#### Scenario: Do not save an unselected line
- **GIVEN** a line has a price or cost discrepancy but no explicit Update action is invoked
- **WHEN** the purchase order is confirmed
- **THEN** price control changes neither product prices nor standard cost
- **AND** standard purchase-order confirmation remains unchanged

#### Scenario: Confirmation enters approval workflow
- **GIVEN** a purchase order requires manager approval and contains price or cost discrepancies
- **WHEN** the user confirms the order and it enters the To Approve state
- **THEN** no product price, standard cost, cost history, lot cost, or snapshot is changed by confirmation
- **AND** later approval does not apply any price-control update

#### Scenario: Multiple selected lines target the same sales-price owner
- **GIVEN** multiple bulk candidates refer to the same product or to variants sharing one sales-price owner
- **WHEN** the user invokes Update All
- **THEN** the fixed line payloads are resolved in purchase-order line order
- **AND** the last applicable payload determines each final shared price and each Standard Price product cost

#### Scenario: Failed confirmation is atomic
- **GIVEN** standard purchase confirmation fails
- **WHEN** the transaction is rolled back
- **THEN** no partial order confirmation remains
- **AND** price control has not written product prices, standard costs, cost history, lot costs, or snapshots

#### Scenario: Confirm without a standard-cost side effect
- **GIVEN** a purchase order contains an initialized Standard Price line with a cost discrepancy
- **WHEN** the order is confirmed, approved, cancelled, reset, locked, or unlocked without an explicit price update
- **THEN** its product prices, standard cost, cost history, lot costs, and line snapshot remain unchanged by that lifecycle action

#### Scenario: Confirm an order without a price side effect
- **GIVEN** a purchase order contains initialized lines with price discrepancies
- **WHEN** the order is confirmed
- **THEN** standard purchase-order confirmation continues
- **AND** no product price or line snapshot is changed by confirmation

#### Scenario: Complete double validation without a price side effect
- **GIVEN** a purchase order requires manager approval and contains price discrepancies
- **WHEN** the order is confirmed and later approved
- **THEN** neither lifecycle action changes product prices or line snapshots

### Requirement: Lifecycle and copied orders
Fill Current Prices, the line-level Update action, and Update All SHALL be available according to line eligibility and discrepancy rules without restriction by the purchase-order state. Cancelling, resetting, confirming, approving, locking, or unlocking an order SHALL NOT revert or automatically reapply prices. Copied orders SHALL start with uninitialized price snapshots.

#### Scenario: Cancel a confirmed order
- **GIVEN** product prices were saved through an explicit price-control action
- **WHEN** the purchase order is later cancelled
- **THEN** the saved reference purchase and sales prices remain unchanged
- **AND** cancellation does not apply another price update

#### Scenario: Confirm again after resetting to draft
- **GIVEN** a confirmed order is reset to draft and still has initialized snapshots
- **WHEN** it is confirmed again
- **THEN** confirmation does not recalculate or apply product prices
- **AND** an explicit Update action remains required for any discrepancy

#### Scenario: Update prices from a non-draft order
- **GIVEN** an initialized differing line belongs to a confirmed, locked, or cancelled purchase order
- **WHEN** the user invokes its Update action or invokes Update All
- **THEN** the calculated product prices and affected snapshots are updated

#### Scenario: Copy a purchase order
- **WHEN** a purchase order containing initialized snapshots is duplicated
- **THEN** every eligible line in the copied order starts without an initialized snapshot
- **AND** the user must invoke Fill Current Prices before using a price-update action

### Requirement: Product write authorization
Price updates SHALL use the acting user's product write permissions and SHALL NOT bypass company or access restrictions. Standard cost SHALL be read and written in the purchase order's company. A failed authorization SHALL roll back the complete line or bulk action.

#### Scenario: User cannot update the product
- **GIVEN** the acting user lacks permission to update an affected product
- **WHEN** the user invokes a line Update action or Update All
- **THEN** the action fails with an access error
- **AND** no reference price, sales price, standard cost, cost history, lot cost, or snapshot is partially updated

#### Scenario: Keep standard cost company-specific
- **GIVEN** a Standard Price product has different costs in two companies
- **WHEN** a user updates prices from an order belonging to one company
- **THEN** only that order company's standard cost is updated
- **AND** the other company's standard cost remains unchanged

#### Scenario: Reject an unauthorized standard-cost update
- **GIVEN** a user cannot write an affected product
- **WHEN** the user invokes an action that would update its standard cost
- **THEN** the action fails with an access error
- **AND** no product price, cost, cost-history, lot-cost, or snapshot change remains

#### Scenario: User cannot fill an affected line
- **GIVEN** the acting user lacks permission to update an affected purchase-order line
- **WHEN** the user invokes Fill Current Prices
- **THEN** the action fails with an access error
- **AND** no partial snapshot updates remain

#### Scenario: User cannot update an affected product
- **GIVEN** the acting user lacks permission to update an affected product
- **WHEN** the user invokes a line Update action or Update All
- **THEN** the action fails with an access error
- **AND** no partial product-price or snapshot updates remain

### Requirement: Explicit current-price snapshots
The system SHALL keep the current reference purchase price, current sales price, current markup, and current standard cost as a persistent snapshot on each eligible purchase-order line. A new, copied, or pre-existing line without a snapshot SHALL remain uninitialized until the user invokes Fill Current Prices. Filling current prices SHALL read the product prices applicable to the order company, derive the markup from those values with the configured default-markup fallback, persist the snapshot, and recalculate dependent prices without changing any product price or inventory value.

#### Scenario: Fill a standard-cost snapshot
- **GIVEN** an eligible line has no initialized snapshot
- **WHEN** the user invokes Fill Current Prices
- **THEN** the line receives the product's current standard cost for the order company together with the existing price snapshot values
- **AND** no product price, lot cost, or inventory value is changed

#### Scenario: Keep the standard-cost snapshot stable
- **GIVEN** an eligible line has an initialized snapshot
- **WHEN** the product's standard cost changes outside the purchase order
- **THEN** the line's current-standard-cost snapshot remains unchanged until prices are filled or refreshed again

#### Scenario: Fill snapshots for an order
- **GIVEN** a purchase order contains eligible product lines without initialized snapshots
- **WHEN** the user invokes Fill Current Prices
- **THEN** every eligible line receives the product's current reference purchase price and sales price
- **AND** its current markup and planned sales price are recalculated from that snapshot
- **AND** no product price is changed

#### Scenario: Derive markup from filled prices
- **GIVEN** a product has a current reference purchase price of `100` and a current sales price of `150`
- **WHEN** the user fills current prices for its purchase-order line
- **THEN** the stored current markup is `50%`

#### Scenario: Use default markup while filling without a reference price
- **GIVEN** a product has no positive reference purchase price and the order company has a default markup of `30%`
- **WHEN** the user fills current prices for its purchase-order line
- **THEN** the stored current markup is `30%`
- **AND** the planned sales price is calculated using that markup

#### Scenario: Fill from the order company
- **GIVEN** a product has different reference purchase prices in two companies
- **WHEN** the user fills current prices on an order belonging to one company
- **THEN** the line snapshot uses that order company's reference purchase price
- **AND** neither company's product price is changed

#### Scenario: Keep a snapshot stable
- **GIVEN** a line has an initialized current-price snapshot
- **WHEN** the corresponding product prices are changed outside the purchase order
- **THEN** the line's snapshot remains unchanged
- **AND** its markup-dependent calculation continues to use the stored markup until the snapshot is filled again

#### Scenario: Refresh an existing snapshot
- **GIVEN** a line has an initialized snapshot that differs from the product's current prices
- **WHEN** the user invokes Fill Current Prices again
- **THEN** the previous snapshot is replaced with the product's current prices
- **AND** the current markup and planned sales price are recalculated

### Requirement: Manual line price update
For an eligible line with an initialized snapshot, the system SHALL offer a line-level Update action whenever the existing reference-purchase-price or sales-price discrepancy exists, or when a Standard Price product's valuation-compatible purchase cost differs from its current-standard-cost snapshot. The comparison SHALL use the order company's currency precision. Invoking the action SHALL write the calculated reference purchase price and sales price to the product and, only for a product currently using Standard Price, write the valuation-compatible purchase cost as its standard cost. The system SHALL then synchronize affected line snapshots with the product prices actually stored.

#### Scenario: Offer Update for only a standard-cost discrepancy
- **GIVEN** an initialized eligible line's reference purchase price and sales price match their calculated values
- **AND** its Standard Price product's calculated purchase cost differs from the current-standard-cost snapshot
- **WHEN** the purchase order is displayed
- **THEN** the line offers the Update action

#### Scenario: Update a Standard Price product from one line
- **GIVEN** an initialized eligible line targets a product currently using Standard Price
- **WHEN** the user invokes Update
- **THEN** the product's standard cost for the order company becomes the line's valuation-compatible purchase cost
- **AND** its reference purchase price and sales price are updated according to the existing price-control rules
- **AND** the affected snapshots reflect the values actually stored

#### Scenario: Retry after a successful standard-cost update
- **GIVEN** an Update action has synchronized all targeted values
- **WHEN** the same action is requested again without another discrepancy
- **THEN** no additional product-price or cost change is applied

#### Scenario: Show the line action for a discrepancy
- **GIVEN** an eligible line has an initialized snapshot
- **AND** at least one calculated price differs from its corresponding snapshot price at company-currency precision
- **WHEN** the purchase order is displayed
- **THEN** the line offers the Update action

#### Scenario: Update both product prices from one line
- **GIVEN** an eligible line offers the Update action
- **WHEN** the user invokes it
- **THEN** the effective purchase price is saved as the product's reference purchase price for the order company
- **AND** the rounded planned sales price is saved as the product's sales price
- **AND** affected line snapshots are synchronized with the prices actually stored

#### Scenario: Hide the line action without a usable discrepancy
- **WHEN** a line has no initialized snapshot, is not an eligible product line, or both calculated prices match its snapshot at company-currency precision
- **THEN** the line does not offer the Update action

### Requirement: Bulk price update
The system SHALL provide an Update All action that applies existing reference purchase and sales price updates to every candidate line and additionally applies standard-cost updates to candidates whose products currently use Standard Price. Candidate payloads SHALL be fixed before any product write, conflicts SHALL be resolved in purchase-order line order, and affected snapshots SHALL be synchronized only after every write succeeds.

#### Scenario: Update standard costs in bulk
- **GIVEN** an order contains multiple initialized Standard Price product lines with standard-cost discrepancies
- **WHEN** the user invokes Update All
- **THEN** each affected product's standard cost for the order company is updated from its valuation-compatible purchase cost
- **AND** the existing reference purchase and sales price updates are also applied

#### Scenario: Resolve repeated Standard Price products deterministically
- **GIVEN** multiple bulk-update candidates target the same Standard Price product with different calculated costs
- **WHEN** the user invokes Update All
- **THEN** the last candidate in purchase-order line order determines the product's final standard cost
- **AND** the bulk action records only that final standard-cost target for the product
- **AND** refreshed snapshots make any remaining earlier-line discrepancy observable

#### Scenario: Roll back a failed standard-cost bulk update
- **GIVEN** a bulk action includes reference, sales, and standard-cost updates
- **WHEN** any targeted write fails
- **THEN** no partial product-price, standard-cost, cost-history, lot-cost, or snapshot update remains

#### Scenario: Update all differing lines
- **GIVEN** an order contains initialized eligible lines with and without price discrepancies
- **WHEN** the user invokes Update All
- **THEN** both calculated prices are saved for every differing line
- **AND** matching, uninitialized, and ineligible lines do not change any product price
- **AND** affected snapshots reflect the final stored product prices

#### Scenario: Resolve shared price owners deterministically
- **GIVEN** multiple differing lines target the same product or variants that share one sales-price owner
- **WHEN** the user invokes Update All
- **THEN** the lines are applied sequentially in purchase-order line order
- **AND** the last applied line determines each final shared price
- **AND** refreshed snapshots make any remaining discrepancy observable

#### Scenario: Roll back a failed bulk update
- **GIVEN** at least one candidate product or line cannot be updated
- **WHEN** Update All fails
- **THEN** no partial product-price or snapshot updates remain

### Requirement: Valuation-compatible purchase cost
For every eligible purchase-order line, the system SHALL calculate a valuation-compatible purchase cost per product base unit in the order company's currency. The calculation SHALL apply the line discount, purchase-tax valuation treatment, purchase unit conversion, order currency conversion, and the order-date exchange rate consistently with standard inventory valuation. This value SHALL remain distinct from the tax-included reference purchase price.

#### Scenario: Exclude recoverable purchase tax from standard cost
- **GIVEN** a purchase-order line contains a recoverable purchase tax
- **WHEN** its valuation-compatible purchase cost is calculated
- **THEN** the recoverable tax is excluded from that cost
- **AND** the tax-included reference purchase price continues to include it

#### Scenario: Include a tax that belongs in inventory value
- **GIVEN** a purchase-order line contains a purchase tax that standard inventory valuation treats as part of cost
- **WHEN** its valuation-compatible purchase cost is calculated
- **THEN** that tax is included in the cost

#### Scenario: Convert purchase unit and currency for standard cost
- **GIVEN** a purchase-order line uses a purchase unit and currency different from the product base unit and company currency
- **WHEN** its valuation-compatible purchase cost is calculated
- **THEN** the result represents one product base unit in the order company's currency
- **AND** currency conversion uses the order date

### Requirement: Inventory valuation isolation by costing method
Price-control actions SHALL NOT write standard cost for products currently using AVCO or FIFO. Their product and lot costs SHALL continue to be determined by standard inventory valuation. A standard-cost write SHALL retain the standard observable accounting and lot-cost consequences of changing cost in Odoo.

#### Scenario: Preserve AVCO cost behavior
- **GIVEN** an eligible line targets a product currently using AVCO
- **WHEN** the user invokes a line or bulk price update
- **THEN** the product's reference purchase price and sales price may be updated
- **AND** its product and lot costs are not changed by price control

#### Scenario: Preserve FIFO cost behavior
- **GIVEN** an eligible line targets a product currently using FIFO
- **WHEN** the user invokes a line or bulk price update
- **THEN** the product's reference purchase price and sales price may be updated
- **AND** its product and lot costs are not changed by price control

#### Scenario: Preserve standard cost consequences
- **GIVEN** an eligible line targets a Standard Price product with existing inventory or lot-specific valuation
- **WHEN** the user explicitly updates its standard cost
- **THEN** the normal standard-cost history and valuation consequences are retained
- **AND** any lot-cost propagation follows standard Odoo behavior
