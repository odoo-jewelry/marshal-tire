## ADDED Requirements

### Requirement: Current-dated stock transfer

The system SHALL transfer eligible on-hand stock from the duplicate product to the canonical product through completed inventory movements dated at the consolidation time, without changing historical product references or movement dates.

#### Scenario: Preview transferable stock
- **GIVEN** the duplicate product has eligible positive stock in valued internal locations
- **WHEN** an authorized user previews consolidation
- **THEN** the preview shows the total quantity and value to transfer
- **AND** the preview identifies the affected locations and remaining FIFO receipt layers

#### Scenario: Consolidate products with positive stock
- **GIVEN** the canonical product has 5 units and the duplicate product has 10 eligible units
- **WHEN** consolidation succeeds
- **THEN** the canonical product has 15 units and the duplicate product has zero units
- **AND** the duplicate is archived according to the normal consolidation lifecycle

#### Scenario: Preserve storage dimensions
- **GIVEN** eligible duplicate stock is distributed across multiple valued internal locations or packages
- **WHEN** consolidation succeeds
- **THEN** the same quantities of the canonical product are available in the corresponding locations and packages

#### Scenario: Preserve historical stock reports
- **GIVEN** the duplicate stock originated from movements completed before consolidation
- **WHEN** consolidation succeeds
- **THEN** the transfer movements are completed at the consolidation time
- **AND** stock reports for times before consolidation remain unchanged

#### Scenario: Consolidate products without stock
- **GIVEN** neither selected product has stock or reservations
- **WHEN** consolidation succeeds
- **THEN** the system completes the existing consolidation behavior without creating stock transfer movements

### Requirement: FIFO value preservation

For eligible FIFO products, the system MUST preserve the duplicate product's inventory value at the consolidation time and SHALL create separately auditable canonical receipt layers for the transferred remaining FIFO quantities.

#### Scenario: Preserve multiple remaining FIFO layer values
- **GIVEN** the duplicate has remaining quantities from receipts with different unit values
- **WHEN** consolidation succeeds
- **THEN** each transferred canonical receipt layer retains the value proportional to its source remaining quantity
- **AND** the canonical product's inventory value after consolidation equals the sum of both products' inventory values immediately before consolidation, subject only to currency rounding

#### Scenario: Append transferred layers to canonical FIFO
- **GIVEN** the canonical product already has positive FIFO stock
- **WHEN** duplicate stock is transferred
- **THEN** the transferred receipt layers follow the canonical product's pre-existing layers in future FIFO valuation order

#### Scenario: Record source receipt audit data
- **WHEN** a transferred canonical receipt layer is created
- **THEN** authorized users can identify its source receipt, original receipt date, duplicate product, transferred quantity, and transferred value
- **AND** the recorded original receipt date does not act as the completion date of the new movement

#### Scenario: Warn about mutable source valuation
- **GIVEN** a remaining source receipt can still be affected by unposted or partial supplier billing
- **WHEN** consolidation is previewed
- **THEN** the preview warns that the transferred value is a snapshot taken at confirmation and later source valuation changes will not be synchronized automatically

### Requirement: Stock transfer eligibility

The system MUST transfer only unreserved, non-negative, company-owned stock whose quantity and FIFO value can be reconciled before confirmation.

#### Scenario: Reject negative or unreconciled stock
- **GIVEN** the duplicate has a negative internal quantity or its transferable quantity cannot be reconciled with its remaining FIFO quantities
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked and the inconsistency is reported

#### Scenario: Reject stock under inventory counting
- **GIVEN** an unfinished inventory count exists for either selected product
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked without applying a partial transfer

#### Scenario: Reject open duplicate stock operations
- **GIVEN** a non-cancelled, non-completed stock movement references the duplicate product
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked until the movement is completed or cancelled

#### Scenario: Reject unsupported ownership or tracking
- **GIVEN** transferable duplicate stock belongs to another owner or either selected product uses lot or serial tracking
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked and the unsupported stock dimension is reported

#### Scenario: Revalidate stock before confirmation
- **GIVEN** an eligible preview was generated
- **WHEN** quantities, reservations, FIFO values, or open movements change before confirmation
- **THEN** confirmation uses current data and refuses any now-ineligible transfer without partial consolidation

## MODIFIED Requirements

### Requirement: Product compatibility safeguards

The system MUST block consolidation when the selected cards are not safely compatible for logical consolidation or, when stock is present, for inventory value transfer.

#### Scenario: Reject multi-variant templates
- **GIVEN** at least one selected card belongs to a template with more than one variant
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and the variant limitation is reported

#### Scenario: Reject incompatible identity and inventory settings
- **GIVEN** the selected cards differ in company ownership, product kind, unit-of-measure category, unit of measure, or storage behavior
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and every incompatible setting is reported

#### Scenario: Reject incompatible stock valuation settings
- **GIVEN** stock must be transferred and the selected cards do not both use compatible FIFO valuation settings and the same inventory adjustment location
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and the incompatible valuation setting is reported

#### Scenario: Reject tracked products
- **GIVEN** at least one selected card uses lot or serial tracking or has lot or serial records
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked without modifying either card

#### Scenario: Reject current stock or reservations
- **GIVEN** either selected card has a reserved quantity or current stock that is not eligible for the defined transfer
- **WHEN** the consolidation preview is evaluated or confirmation is attempted
- **THEN** consolidation is blocked and the unsupported stock or reservation is reported

#### Scenario: Accept eligible current stock
- **GIVEN** the duplicate has positive stock that satisfies all stock transfer eligibility rules
- **WHEN** the consolidation preview is evaluated
- **THEN** current stock is presented as transferable data instead of a blocker

#### Scenario: Revalidate before confirmation
- **GIVEN** an eligible preview has already been generated
- **WHEN** product or operational data changes before confirmation and makes the pair ineligible
- **THEN** confirmation is refused using the current data and no partial consolidation is applied

### Requirement: Authorization, audit, and atomicity

Consolidation, including any related inventory transfer, MUST be restricted, explicitly confirmed, auditable, and atomic.

#### Scenario: Reject an unauthorized user
- **WHEN** a user without product-consolidation permission attempts to preview or confirm consolidation through the user interface or server API
- **THEN** access is denied and no product or stock data is changed

#### Scenario: Confirm an irreversible action
- **GIVEN** the preview has no blockers and identifies stock to transfer
- **WHEN** the user requests consolidation
- **THEN** the system requires explicit final confirmation that stock will be transferred and the duplicate will be archived

#### Scenario: Cancel before stock transfer
- **GIVEN** a stock-aware consolidation preview is open
- **WHEN** the user cancels or closes it without final confirmation
- **THEN** no stock movement, valuation change, product change, or audit record is created

#### Scenario: Record a successful consolidation
- **WHEN** stock-aware consolidation succeeds
- **THEN** the canonical card records who performed it, when it occurred, which duplicate was consolidated, and which transfer movements were created

#### Scenario: Roll back a failed consolidation
- **GIVEN** validation, stock movement completion, valuation, or any later consolidation write fails
- **WHEN** the operation ends with an error
- **THEN** all changes from that attempt are rolled back, including stock quantities, movement values, configuration, aliases, links, and archival state

#### Scenario: Retry after a failed attempt
- **GIVEN** a previous consolidation attempt failed without partial changes
- **WHEN** the blocking cause is resolved and an authorized user retries
- **THEN** the system revalidates current stock and can complete the consolidation once

### Requirement: Unchanged standard product behavior

The system SHALL preserve standard product and stock behavior for cards that have not been consolidated and for workflows that do not invoke consolidation.

#### Scenario: Use an ordinary product
- **GIVEN** a product has neither been consolidated nor registered as a canonical target
- **WHEN** users search, buy, sell, stock, value, archive, unarchive, import, or report that product without invoking consolidation
- **THEN** standard Odoo behavior remains unchanged
