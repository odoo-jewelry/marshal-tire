## ADDED Requirements

### Requirement: Explicit current-price snapshots
The system SHALL keep the current reference purchase price, current sales price, and current markup as a persistent snapshot on each eligible purchase-order line. A new, copied, or pre-existing line without a snapshot SHALL remain uninitialized until the user invokes Fill Current Prices. Filling current prices SHALL read the product prices applicable to the order company, derive the markup from those values with the configured default-markup fallback, persist the snapshot, and recalculate the planned sales price without changing any product price.

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
For an eligible line with an initialized snapshot, the system SHALL offer a line-level Update action whenever either the effective purchase price differs from the snapshot purchase price or the rounded planned sales price differs from the snapshot sales price. The comparison SHALL use the order company's currency precision. Invoking the action SHALL write both calculated prices to the product and then synchronize affected line snapshots with the product prices actually stored.

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
The system SHALL provide an Update All action on a purchase order. The action SHALL apply both calculated prices for every eligible line that has an initialized snapshot and a price discrepancy, leave all other lines unchanged, process candidates in purchase-order line order, and synchronize affected snapshots after all product writes succeed.

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

## MODIFIED Requirements

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

### Requirement: Planned sales price and upward rounding
For an initialized line, the system SHALL calculate the unrounded planned sales price as the effective purchase price multiplied by one plus the stored current markup percentage. It SHALL round any positive result upward to the nearest multiple of the configured rounding step. An uninitialized line SHALL NOT present a usable planned sales price or price-update action.

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

#### Scenario: Do not calculate from an absent snapshot
- **GIVEN** an eligible line has not been filled with current prices
- **WHEN** its commercial terms change
- **THEN** the line remains uninitialized
- **AND** it does not offer a product-price update based on an implicit markup

### Requirement: Explicit price saving on confirmation
The system SHALL NOT save reference purchase prices or sales prices as a side effect of confirming or approving a purchase order. Product prices SHALL change only when a user explicitly invokes a line-level or order-level price update action.

#### Scenario: Save an explicitly selected line
- **GIVEN** an initialized line has a price discrepancy
- **WHEN** the user invokes the line-level Update action
- **THEN** the product reference purchase price and sales price are updated from the recalculated line values
- **AND** no purchase-order lifecycle transition is required

#### Scenario: Do not save an unselected line
- **GIVEN** an initialized line has a price discrepancy but no explicit Update action is invoked
- **WHEN** the purchase order is confirmed
- **THEN** neither the reference purchase price nor the sales price is changed by price control
- **AND** standard purchase-order confirmation remains unchanged

#### Scenario: Confirmation enters approval workflow
- **GIVEN** a purchase order requires manager approval and contains initialized lines with price discrepancies
- **WHEN** the user confirms the order and it enters the To Approve state
- **THEN** no product price or snapshot is changed by confirmation
- **AND** later approval does not apply any price-control update

#### Scenario: Multiple selected lines target the same sales-price owner
- **GIVEN** multiple initialized differing lines refer to the same product or to variants sharing one sales-price owner
- **WHEN** the user invokes Update All
- **THEN** the fixed line payloads are applied sequentially in purchase-order line order
- **AND** the last applied line determines the final shared sales price

#### Scenario: Failed confirmation is atomic
- **GIVEN** standard purchase confirmation fails
- **WHEN** the transaction is rolled back
- **THEN** no partial order confirmation remains
- **AND** price control has not written any product price or line snapshot

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
Filling snapshots and saving product prices SHALL use the acting user's standard purchase-line and product permissions and SHALL NOT bypass company or access restrictions. Each invoked action SHALL be atomic.

#### Scenario: User cannot update the product
- **GIVEN** the acting user lacks permission to update an affected product
- **WHEN** the user invokes a line Update action or Update All
- **THEN** the action fails with an access error
- **AND** no selected product or line snapshot is partially updated

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
