## ADDED Requirements

### Requirement: Refresh snapshots without rewriting unchanged records
Fill Current Prices and the snapshot refresh following Update or Update All SHALL preserve the last-modification metadata of eligible order lines whose complete resulting snapshot and manual-price state are unchanged. The system SHALL still refresh every eligible line in the affected orders when an update has candidates, including lines whose product prices changed outside the selected line. Fill Current Prices SHALL retain its explicit initialization and manual-price reset behavior.

#### Scenario: Refresh one changed line in a large order
- **GIVEN** an order has 266 initialized eligible lines for distinct products and all snapshots are current
- **WHEN** Update changes the sales price of one line's product
- **THEN** that line's snapshot reflects the stored price
- **AND** the other 265 lines retain their snapshot values and last-modification metadata

#### Scenario: Refresh stale and shared-price snapshots throughout the order
- **GIVEN** an order contains another line for the updated product, a variant sharing its sales-price owner, and an unrelated line with stale current prices
- **WHEN** a selected line is updated
- **THEN** every eligible line's snapshot reflects its applicable current product values after the action
- **AND** the refresh preserves manually entered New Sale values

#### Scenario: Repeat Fill with already current values
- **GIVEN** every eligible line is initialized with current snapshots and no manual-price override state
- **WHEN** Fill Current Prices is invoked again without any relevant source change
- **THEN** the lines retain their last-modification metadata and current values

#### Scenario: Initialize an all-zero snapshot
- **GIVEN** an eligible line is uninitialized and its resulting numeric snapshot values are all zero
- **WHEN** Fill Current Prices is invoked
- **THEN** the line becomes initialized even though the numeric values do not change

#### Scenario: Reset a manual price even when snapshot numbers match
- **GIVEN** a line has current snapshot numbers and a manually entered New Sale
- **WHEN** Fill Current Prices is invoked
- **THEN** the manual override is cleared and automatic New Sale is restored

### Requirement: Avoid redundant product-price changes
For existing update candidates, Update and Update All SHALL leave already matching product-price values unwritten and SHALL preserve product last-modification metadata when no applicable product value changes. Matching SHALL respect the precision with which each value is stored, without changing the existing currency-precision rule for candidate selection. The system SHALL retain fixed candidate targets, sequential conflict resolution, and normal consequences for values that actually change.

#### Scenario: Update from a stale snapshot when the product already matches
- **GIVEN** an initialized line has a snapshot discrepancy but its applicable target prices are already stored on the product
- **WHEN** Update is invoked by an authorized user
- **THEN** the product retains its last-modification metadata and gains no cost-history entry
- **AND** the order snapshots become current

#### Scenario: Apply only the differing product value
- **GIVEN** a Standard Price candidate's target cost is already stored and its target sales price differs
- **WHEN** Update is invoked
- **THEN** the sales price changes and no redundant cost update or cost-history entry occurs

#### Scenario: Preserve ordered conflicts between shared price owners
- **GIVEN** several bulk candidates share a product or sales-price owner and some target values initially match
- **WHEN** Update All is invoked
- **THEN** each candidate is evaluated against the values resulting from earlier candidates
- **AND** the final shared values follow the existing last-applicable-line rule
- **AND** earlier conflicting lines remain visibly discrepant after refresh

### Requirement: Preserve access and transaction behavior during optimized updates
Suppressing unchanged writes SHALL NOT bypass existing write authorization, company isolation, valuation rules, or transaction rollback. An action with no update candidates SHALL retain its existing no-change behavior. Standard purchase processing SHALL remain unchanged when price-control actions are not invoked.

#### Scenario: Reject an unauthorized candidate that already matches the product
- **GIVEN** an initialized candidate has stale snapshots, matching product target values, and the acting user lacks write access to an affected product or protected price field
- **WHEN** Update or Update All is invoked
- **THEN** the action fails with an access error and no partial snapshot change remains

#### Scenario: Reject an unauthorized unchanged snapshot refresh
- **GIVEN** an eligible line already has current snapshot values but the acting user lacks permission to write that line or an affected snapshot field
- **WHEN** Fill Current Prices or a candidate-bearing update requiring that line's refresh is invoked
- **THEN** the complete action fails with an access error

#### Scenario: Retry without candidates
- **GIVEN** a successful update leaves no applicable snapshot discrepancy
- **WHEN** Update or Update All is invoked again
- **THEN** no product value, snapshot, cost history, or last-modification metadata changes

#### Scenario: Roll back changes preceding a later failure
- **GIVEN** a bulk action includes unchanged candidates and a changed candidate followed by a candidate that fails
- **WHEN** Update All is invoked
- **THEN** the entire action is rolled back, including product values, cost history, and snapshots

#### Scenario: Preserve standard purchase processing
- **WHEN** a user saves, confirms, approves, cancels, resets, locks, unlocks, or copies an order without invoking price-control actions
- **THEN** standard purchase processing and the existing price-control lifecycle rules remain unchanged
