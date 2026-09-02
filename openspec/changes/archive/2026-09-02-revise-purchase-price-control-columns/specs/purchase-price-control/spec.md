## ADDED Requirements

### Requirement: Compact price-control column layout
For every eligible purchase-order product line, the system SHALL present the price columns in this order: the standard `Unit Price`, `Current Cost`, `Markup`, `Current Sale`, and `New Sale`. `Current Cost` SHALL represent the product's current company-specific cost, `Current Sale` SHALL represent its current sales price, and `New Sale` SHALL represent the planned sales price. The price-control interface SHALL NOT display a separate reference purchase price, tax-included purchase price, or valuation-cost column.

#### Scenario: Display the required columns in order
- **GIVEN** a purchase order contains an eligible product line
- **WHEN** the user opens the order form
- **THEN** the line displays `Unit Price`, `Current Cost`, `Markup`, `Current Sale`, and `New Sale` in that order
- **AND** `Unit Price` remains the standard purchase-order field

#### Scenario: Do not add price columns to non-product lines
- **WHEN** a purchase order contains a section, subsection, note, or down-payment line
- **THEN** the added price-control values are not displayed as usable values for that line

### Requirement: Tax-independent custom purchase basis
The purchase basis used by price control SHALL apply the line discount, purchase-unit conversion, order-currency conversion, company, and order-date exchange rate, but SHALL NOT include or otherwise depend on the line's purchase taxes. Standard Odoo tax fields, totals, invoices, accounting entries, and inventory valuation behavior MUST remain unchanged.

#### Scenario: Ignore purchase tax in price-control calculations
- **GIVEN** two otherwise identical purchase-order lines have different purchase taxes
- **WHEN** price control calculates their automatic new sales prices
- **THEN** both lines use the same tax-independent purchase basis
- **AND** their standard Odoo tax totals continue to reflect their respective taxes

#### Scenario: Apply discount without applying tax
- **GIVEN** a line has a unit price of `100`, a discount of `10%`, and a purchase tax of `20%`
- **WHEN** price control calculates its purchase basis
- **THEN** the basis equals `90` before unit and currency conversion

#### Scenario: Convert purchase unit and currency
- **GIVEN** a line uses a purchase unit different from the product base unit and a currency different from the company currency
- **WHEN** price control calculates its purchase basis
- **THEN** the basis represents one product base unit in the order company's currency
- **AND** conversion uses the order date

### Requirement: Safe transition of existing price snapshots
When the module is upgraded, the system SHALL align every existing initialized price snapshot with the new cost-based markup semantics without changing products, purchase-order lifecycle state, taxes, inventory, or accounting records. Fields removed from price control and their legacy values SHALL be deleted as part of the module schema cleanup.

#### Scenario: Recalculate an existing snapshot markup
- **GIVEN** an initialized pre-upgrade line stores Current Cost of `100` and Current Sale of `150`
- **WHEN** the module is upgraded
- **THEN** its stored Markup becomes `50%`
- **AND** any exact manually entered `New Sale` value remains unchanged

#### Scenario: Preserve business records during upgrade
- **GIVEN** the database contains price-control data on existing purchase orders
- **WHEN** the module is upgraded
- **THEN** no product price, purchase-order state, inventory value, accounting entry, or tax value is changed
- **AND** only the obsolete custom fields and their stored values are removed

## MODIFIED Requirements

### Requirement: Purchase-line price-control information
For every eligible product line, regardless of purchase-order state, the system SHALL display the current-cost snapshot, current markup percentage, current sales-price snapshot, rounded new sales price, and the applicable manual price action. Section, subsection, note, and down-payment lines SHALL NOT participate in price control.

#### Scenario: Display markup based on a saved reference price
- **GIVEN** a product has a current cost of `100` and a current sales price of `150`
- **WHEN** the user invokes Fill Current Prices for its purchase-order line
- **THEN** the stored markup is displayed as `50%`

#### Scenario: Use the default markup without a reference price
- **GIVEN** a product has no positive current cost and the company default markup is `30%`
- **WHEN** the user invokes Fill Current Prices for its purchase-order line
- **THEN** the stored markup is `30%`
- **AND** the automatic new sales price is calculated using `30%`

#### Scenario: Display initialized price-control information in any state
- **GIVEN** an eligible line has an initialized snapshot
- **WHEN** its purchase order is draft, sent, awaiting approval, confirmed, locked, cancelled, or reset to draft
- **THEN** the line displays its snapshot and calculated price-control values
- **AND** manual actions are governed by price discrepancies rather than the order state

#### Scenario: Ignore non-product lines
- **WHEN** a purchase order contains a section, subsection, note, or down-payment line
- **THEN** that line has no current-price snapshot actions
- **AND** it cannot update any product price

### Requirement: Planned sales price and upward rounding
For an initialized eligible line, the system SHALL calculate the automatic `New Sale` value from the tax-independent purchase basis and stored markup, applying the configured upward rounding step. The user SHALL be able to enter `New Sale` directly, and the system SHALL preserve the exact manual value without changing the stored markup. Changes to taxes SHALL NOT change either an automatic or manual `New Sale` value. Invoking Fill Current Prices SHALL clear a manual value and restore automatic calculation. An uninitialized line SHALL NOT accept a usable manual value or offer an update action.

#### Scenario: Round upward to a whole-price step
- **GIVEN** an initialized line has a tax-independent purchase basis of `100`, a markup of `21%`, and a rounding step of `10`
- **WHEN** `New Sale` is calculated
- **THEN** it equals `130`

#### Scenario: Preserve an exact multiple
- **GIVEN** an initialized line has an unrounded `New Sale` of `120` and a rounding step of `10`
- **WHEN** `New Sale` is calculated
- **THEN** it remains `120`

#### Scenario: Round upward to a fractional step
- **GIVEN** an initialized line has an unrounded `New Sale` of `12.341` and a rounding step of `0.10`
- **WHEN** `New Sale` is calculated
- **THEN** it equals `12.40`

#### Scenario: Enter a planned sales price directly
- **GIVEN** an initialized line has a calculated `New Sale`
- **WHEN** the user enters `12` directly
- **THEN** `New Sale` remains exactly `12`
- **AND** the line markup remains unchanged
- **AND** no product price is changed by editing the line

#### Scenario: Preserve a manual price after the purchase-price basis changes
- **GIVEN** a user entered `New Sale` of `12`
- **WHEN** the unit price, discount, purchase unit, currency, company, order date, or taxes change
- **THEN** `New Sale` remains exactly `12`
- **AND** the line markup remains unchanged

#### Scenario: Ignore a tax change
- **GIVEN** an initialized eligible line has an automatic or manual `New Sale` value
- **WHEN** its purchase taxes change without any other commercial-term change
- **THEN** its `New Sale` value remains unchanged
- **AND** standard Odoo recalculates its tax amounts normally

#### Scenario: Restore automatic calculation explicitly
- **GIVEN** a line has a manually entered `New Sale` value
- **WHEN** the user invokes Fill Current Prices
- **THEN** the manual value is cleared
- **AND** `New Sale` is recalculated from the tax-independent purchase basis and refreshed markup
- **AND** the configured upward rounding rule is applied

#### Scenario: Keep automatic calculation when manual entry is not used
- **GIVEN** an initialized eligible line has no manual `New Sale`
- **WHEN** its unit price, discount, purchase unit, currency, company, or order date changes
- **THEN** `New Sale` is recalculated from the tax-independent purchase basis and stored markup

#### Scenario: Do not calculate from an absent snapshot
- **GIVEN** an eligible line has not been filled with current prices
- **WHEN** the user edits its commercial terms
- **THEN** the line remains uninitialized
- **AND** it does not offer a usable manual `New Sale` or a product-price update

### Requirement: Explicit current-price snapshots
The system SHALL keep current cost, current sales price, and current markup as a persistent snapshot on each eligible purchase-order line. A new, copied, or pre-existing line without a snapshot SHALL remain uninitialized until the user invokes Fill Current Prices. Filling SHALL read the product cost and sales price applicable to the order company, derive markup from those values with the configured default-markup fallback, persist the snapshot, and recalculate `New Sale` without changing any product price or inventory value.

#### Scenario: Fill a standard-cost snapshot
- **GIVEN** an eligible line has no initialized snapshot
- **WHEN** the user invokes Fill Current Prices
- **THEN** the line receives the product's current company-specific cost and sales price
- **AND** its markup and `New Sale` are calculated
- **AND** no product price, lot cost, or inventory value is changed

#### Scenario: Keep the standard-cost snapshot stable
- **GIVEN** an initialized line stores Current Cost
- **WHEN** the product cost changes outside the purchase order
- **THEN** Current Cost remains unchanged until Fill Current Prices is invoked again

#### Scenario: Fill snapshots for an order
- **GIVEN** an order contains eligible lines without initialized snapshots
- **WHEN** the user invokes Fill Current Prices
- **THEN** every eligible line receives Current Cost and Current Sale
- **AND** its Markup and New Sale are calculated without changing the product

#### Scenario: Derive markup from filled prices
- **GIVEN** a product has a current cost of `100` and a current sales price of `150`
- **WHEN** the user fills current prices for its purchase-order line
- **THEN** the stored markup is `50%`

#### Scenario: Use default markup while filling without a reference price
- **GIVEN** a product has no positive current cost and the company default markup is `30%`
- **WHEN** the user fills current prices for its purchase-order line
- **THEN** the stored markup is `30%`
- **AND** automatic `New Sale` uses that markup

#### Scenario: Fill from the order company
- **GIVEN** a product has different costs in two companies
- **WHEN** the user fills prices on an order belonging to one company
- **THEN** Current Cost uses that order company's product cost
- **AND** neither company's product values are changed

#### Scenario: Keep a snapshot stable
- **GIVEN** a line has an initialized snapshot
- **WHEN** the corresponding product cost or sales price changes outside the purchase order
- **THEN** the line snapshot remains unchanged until Fill Current Prices is invoked again

#### Scenario: Refresh an existing snapshot
- **GIVEN** an initialized snapshot differs from the product's current cost or sales price
- **WHEN** the user invokes Fill Current Prices again
- **THEN** the snapshot is replaced with the current company-specific values
- **AND** markup and automatic `New Sale` are recalculated

### Requirement: Explicit price saving on confirmation
The system SHALL NOT save sales prices or standard costs as a side effect of confirming, approving, cancelling, resetting, locking, or unlocking a purchase order. Price control SHALL change values only when a user explicitly invokes a line-level or order-level update action. An update SHALL write `New Sale` as the product sales price and, only for a product currently using Standard Price, write the tax-independent purchase basis as its company-specific cost.

#### Scenario: Save an explicitly selected line
- **GIVEN** an initialized Standard Price line has a sales-price or cost discrepancy
- **WHEN** the user invokes its Update action
- **THEN** the product sales price and company-specific standard cost are updated from the line values
- **AND** no purchase-order lifecycle transition is required

#### Scenario: Do not save an unselected line
- **GIVEN** a line has a price or cost discrepancy but no explicit update action is invoked
- **WHEN** the purchase order is confirmed
- **THEN** price control changes neither product sales price nor standard cost

#### Scenario: Confirmation enters approval workflow
- **GIVEN** an order requires manager approval and contains price or cost discrepancies
- **WHEN** the user confirms the order and it enters To Approve
- **THEN** no product price, standard cost, inventory value, or snapshot is changed by confirmation
- **AND** later approval does not apply any price-control update

#### Scenario: Multiple selected lines target the same sales-price owner
- **GIVEN** multiple bulk candidates target the same product or a shared sales-price owner
- **WHEN** the user invokes Update All
- **THEN** fixed line payloads are resolved in purchase-order line order
- **AND** the last applicable payload determines each final shared value

#### Scenario: Failed confirmation is atomic
- **GIVEN** standard purchase confirmation fails
- **WHEN** the transaction is rolled back
- **THEN** no partial order confirmation remains
- **AND** price control has written no product value or snapshot

#### Scenario: Confirm without a standard-cost side effect
- **GIVEN** an initialized Standard Price line has a cost discrepancy
- **WHEN** the order is confirmed, approved, cancelled, reset, locked, or unlocked without an explicit update
- **THEN** its standard cost, inventory value, and line snapshot remain unchanged by that lifecycle action

#### Scenario: Confirm an order without a price side effect
- **GIVEN** an order contains initialized lines with discrepancies
- **WHEN** the order is confirmed
- **THEN** standard purchase-order processing continues
- **AND** price control changes no product price, cost, inventory value, or line snapshot

#### Scenario: Complete double validation without a price side effect
- **GIVEN** an order requires manager approval and contains discrepancies
- **WHEN** the order is confirmed and later approved
- **THEN** neither lifecycle action changes product values or line snapshots

### Requirement: Manual line price update
For an initialized eligible line, the system SHALL offer Update when `New Sale` differs from the current-sales-price snapshot or, for a Standard Price product, when the tax-independent purchase basis differs from the current-cost snapshot. Comparisons SHALL use the order company's currency precision. Update SHALL write the planned sales price and, only for Standard Price, the company-specific cost, then refresh affected snapshots from values actually stored.

#### Scenario: Show the line action for a discrepancy
- **GIVEN** an initialized line's `New Sale` differs from `Current Sale`
- **WHEN** the purchase order is displayed
- **THEN** the line offers Update

#### Scenario: Offer Update for only a standard-cost discrepancy
- **GIVEN** an initialized Standard Price line's sales prices match
- **AND** its tax-independent purchase basis differs from `Current Cost`
- **WHEN** the purchase order is displayed
- **THEN** the line offers Update

#### Scenario: Update a Standard Price product from one line
- **GIVEN** an initialized eligible line targets a Standard Price product
- **WHEN** the user invokes Update
- **THEN** the product's sales price becomes `New Sale`
- **AND** its company-specific standard cost becomes the tax-independent purchase basis
- **AND** affected snapshots reflect values actually stored

#### Scenario: Do not write AVCO or FIFO cost
- **GIVEN** an initialized eligible line targets an AVCO or FIFO product
- **WHEN** the user invokes Update
- **THEN** its sales price may be updated
- **AND** its product and lot costs are not changed by price control

#### Scenario: Retry after a successful standard-cost update
- **GIVEN** Update synchronized all targeted values
- **WHEN** no discrepancy remains
- **THEN** the line no longer offers Update

#### Scenario: Update both product prices from one line
- **GIVEN** an initialized eligible line has applicable sales-price and Standard Price cost discrepancies
- **WHEN** the user invokes Update
- **THEN** `New Sale` is saved as the product sales price
- **AND** the tax-independent purchase basis is saved as the company-specific standard cost
- **AND** affected snapshots are synchronized

#### Scenario: Hide the line action without a usable discrepancy
- **WHEN** a line is uninitialized, ineligible, or all applicable values match at company-currency precision
- **THEN** the line does not offer Update

### Requirement: Bulk price update
The system SHALL provide Update All for every initialized eligible line with a sales-price discrepancy or an applicable Standard Price cost discrepancy. Candidate values SHALL be fixed before any product write, conflicts SHALL be resolved in purchase-order line order, and snapshots SHALL be refreshed only after every write succeeds. The action SHALL NOT write AVCO or FIFO costs.

#### Scenario: Update standard costs in bulk
- **GIVEN** an order contains initialized eligible lines with and without discrepancies
- **WHEN** the user invokes Update All
- **THEN** sales prices are updated for differing candidates
- **AND** Standard Price costs are updated for applicable cost candidates
- **AND** matching, uninitialized, and ineligible lines change no product value

#### Scenario: Resolve repeated Standard Price products deterministically
- **GIVEN** multiple candidates target the same product with different values
- **WHEN** the user invokes Update All
- **THEN** the last candidate in purchase-order line order determines each final shared value
- **AND** refreshed snapshots make any earlier-line discrepancy observable

#### Scenario: Roll back a failed standard-cost bulk update
- **GIVEN** at least one candidate cannot be updated
- **WHEN** Update All fails
- **THEN** no partial sales-price, standard-cost, inventory-value, or snapshot update remains

#### Scenario: Update all differing lines
- **GIVEN** an order contains initialized eligible lines with and without discrepancies
- **WHEN** the user invokes Update All
- **THEN** every differing candidate receives its applicable updates
- **AND** matching, uninitialized, and ineligible lines change no product value

#### Scenario: Resolve shared price owners deterministically
- **GIVEN** multiple candidates target the same product or a shared sales-price owner
- **WHEN** the user invokes Update All
- **THEN** lines are applied sequentially in purchase-order line order
- **AND** the last applicable line determines each final shared value

#### Scenario: Roll back a failed bulk update
- **GIVEN** at least one candidate product or line cannot be updated
- **WHEN** Update All fails
- **THEN** no partial product-value or snapshot update remains

### Requirement: Lifecycle and copied orders
Fill Current Prices, Update, and Update All SHALL be available according to line eligibility and discrepancy rules without restriction by purchase-order state. Cancelling, resetting, confirming, approving, locking, or unlocking an order SHALL NOT revert or automatically apply prices. Copied orders SHALL start with uninitialized price snapshots.

#### Scenario: Cancel a confirmed order
- **GIVEN** product values were saved through an explicit price-control action
- **WHEN** the purchase order is later cancelled
- **THEN** the saved sales price and any applicable Standard Price cost remain unchanged
- **AND** cancellation does not apply another price update

#### Scenario: Confirm again after resetting to draft
- **GIVEN** a confirmed order is reset to draft and still has initialized snapshots
- **WHEN** it is confirmed again
- **THEN** confirmation does not recalculate or apply product prices
- **AND** an explicit Update action remains required for any discrepancy

#### Scenario: Update prices from a non-draft order
- **GIVEN** an initialized differing line belongs to a confirmed, locked, or cancelled purchase order
- **WHEN** the user invokes Update or Update All
- **THEN** the applicable product values and affected snapshots are updated

#### Scenario: Copy a purchase order
- **WHEN** a purchase order containing initialized snapshots is duplicated
- **THEN** every eligible line in the copied order starts without an initialized snapshot
- **AND** the user must invoke Fill Current Prices before using an update action

### Requirement: Product write authorization
Price updates SHALL use the acting user's product write permissions and SHALL NOT bypass company or access restrictions. Current Cost SHALL be read and Standard Price cost SHALL be written in the purchase order's company. A failed authorization SHALL roll back the complete line or bulk action.

#### Scenario: User cannot update an affected product
- **GIVEN** the acting user lacks permission to update an affected product
- **WHEN** the user invokes Update or Update All
- **THEN** the action fails with an access error
- **AND** no sales price, standard cost, inventory value, or snapshot is partially updated

#### Scenario: Keep standard cost company-specific
- **GIVEN** a product has different costs in two companies
- **WHEN** a user fills or updates prices from an order belonging to one company
- **THEN** Current Cost and any Standard Price cost update use only that order company
- **AND** the other company's cost remains unchanged

#### Scenario: User cannot update the product
- **GIVEN** the acting user lacks permission to update an affected product
- **WHEN** the user invokes Update or Update All
- **THEN** the action fails with an access error
- **AND** no product value or snapshot is partially updated

#### Scenario: Reject an unauthorized standard-cost update
- **GIVEN** the acting user cannot write an affected Standard Price product
- **WHEN** an action would update its standard cost
- **THEN** the action fails with an access error
- **AND** no sales price, standard cost, inventory value, or snapshot change remains

#### Scenario: User cannot fill an affected line
- **GIVEN** the acting user lacks permission to update an affected purchase-order line
- **WHEN** the user invokes Fill Current Prices
- **THEN** the action fails with an access error
- **AND** no partial snapshot updates remain

### Requirement: Inventory valuation isolation by costing method
Price-control actions SHALL NOT write cost for products currently using AVCO or FIFO. Their product and lot costs SHALL continue to be determined by standard inventory valuation. A Standard Price cost write SHALL retain the standard observable accounting and lot-cost consequences of changing cost in Odoo.

#### Scenario: Preserve AVCO cost behavior
- **GIVEN** an eligible line targets an AVCO product
- **WHEN** the user invokes a line or bulk price update
- **THEN** the product sales price may be updated
- **AND** its product and lot costs are not changed by price control

#### Scenario: Preserve FIFO cost behavior
- **GIVEN** an eligible line targets a FIFO product
- **WHEN** the user invokes a line or bulk price update
- **THEN** the product sales price may be updated
- **AND** its product and lot costs are not changed by price control

#### Scenario: Preserve standard cost consequences
- **GIVEN** an eligible line targets a Standard Price product with existing inventory or lot-specific valuation
- **WHEN** the user explicitly updates its cost
- **THEN** normal Standard Price cost history and valuation consequences are retained
- **AND** any lot-cost propagation follows standard Odoo behavior

## REMOVED Requirements

### Requirement: Independent reference purchase price
**Reason**: The simplified purchase-order workflow uses the standard `Unit Price` as its visible purchase-price source and no longer exposes or updates a separate reference purchase price.

**Migration**: Existing stored reference-price data is intentionally discarded with the removed custom field and SHALL NOT be transferred to another business field.

### Requirement: Effective purchase price calculation
**Reason**: The tax-included effective purchase price conflicts with the required tax-independent custom calculation and is removed from the price-control interface and behavior.

**Migration**: Existing orders require no data conversion; automatic `New Sale` values SHALL be recalculated from the new tax-independent basis when read.

### Requirement: Valuation-compatible purchase cost
**Reason**: A separate custom valuation-cost indicator is no longer required. Standard Odoo remains the source of truth for tax treatment and inventory valuation, while explicit Standard Price updates use the tax-independent purchase basis.

**Migration**: No accounting or inventory records SHALL be rewritten during module upgrade.
