## MODIFIED Requirements

### Requirement: Controlled consolidation selection

The system SHALL offer two explicitly named modes: current-stock consolidation and full-history consolidation. Current-stock consolidation SHALL retain its existing active-card selection and behavior and SHALL be the compatibility default for existing callers that omit a mode. Full-history consolidation SHALL require an explicit selection; an authorized user SHALL select one active canonical single-variant card and one active or archived duplicate. For full-history conversion of previously consolidated cards, the system SHALL resolve and preview every unconverted source already belonging to that canonical card as one atomic conversion scope. It MUST NOT require reactivating an archived source. The interface and public API SHALL retain both modes, and preview SHALL identify the selected mode and its effect on historical reports. Changing the mode SHALL invalidate the previous preview and require renewed confirmation.

#### Scenario: M01 Preview a new pair
- **WHEN** an authorized user explicitly selects full-history mode with an active canonical card and an eligible active or archived duplicate
- **THEN** preview identifies the source cards, documents, movements, quantity reconciliation, earliest affected cost date and blockers
- **AND** preview changes no business records

#### Scenario: M02 Open conversion from an archived source
- **GIVEN** an archived source belongs to a previous consolidation
- **WHEN** the user opens full history consolidation from that source
- **THEN** its existing canonical card and all its unconverted sources are included in preview without reactivation

#### Scenario: M03 Reject invalid identities
- **WHEN** selection contains the same card twice, an inactive canonical card, a merged source as canonical, a source belonging to another canonical card, or an unsupported merge chain
- **THEN** consolidation is rejected with the conflicting relationship identified

#### Scenario: M04 Select and confirm a consolidation mode
- **WHEN** a user selects or changes the consolidation mode
- **THEN** preview and confirmation describe either current-stock transfer with preserved source history or full-history transfer using original dates
- **AND** changing mode invalidates the previous preview and requires a new review

#### Scenario: M30 Preserve existing callers
- **WHEN** an existing public caller omits the consolidation mode
- **THEN** the existing current-stock behavior is used and no full-history rewrite is silently selected

#### Scenario: Preview an eligible pair
- **GIVEN** current-stock consolidation is selected
- **AND** two active single-variant product cards are selected
- **WHEN** an authorized user starts consolidation and chooses the canonical card
- **THEN** the system shows a preview identifying the canonical card, duplicate card, transferable data, preserved references, and any blockers

#### Scenario: Reject an invalid selection count
- **GIVEN** current-stock consolidation is selected
- **WHEN** a user starts consolidation with fewer or more than two product cards
- **THEN** the system refuses to open a valid consolidation preview and explains that exactly two cards are required

#### Scenario: Cancel before confirmation
- **GIVEN** current-stock consolidation is selected
- **AND** a consolidation preview is open
- **WHEN** the user cancels or closes it without confirmation
- **THEN** neither product card nor any related record is changed

### Requirement: Product compatibility safeguards

Current-stock mode SHALL retain its existing compatibility and stock-transfer safeguards. Full-history mode MUST additionally prove compatibility and complete coverage of the affected operational history before applying a merge. In full-history mode, supported stocked products SHALL be single-variant, untracked, company-owned products with identical units and compatible FIFO and periodic valuation settings. Protected financial or analytic links, locked periods, reservations, unfinished stock operations, inventory counts, unreconciled quantities and unhandled operational references SHALL block the whole operation with identified records. Shared cards with history in another company MUST NOT be partly merged. Compatible cards without stock history SHALL retain their existing configuration-only eligibility.

#### Scenario: M05 Reject incompatible inventory identity
- **WHEN** selected cards have incompatible companies, units, product types or valuation settings, multiple variants, lots or serial tracking
- **THEN** preview identifies each incompatibility and application is unavailable

#### Scenario: M06 Reject incomplete operational coverage
- **GIVEN** the proposed scope contains reservations, unfinished stock operations, inventory counts, unsupported ownership, unhandled return links or other unhandled operational references
- **WHEN** consolidation is previewed
- **THEN** the blocking records are reported and no supported subset is offered as a complete merge

#### Scenario: M07 Preserve protected financial history
- **GIVEN** changing a product reference would affect a protected accounting or analytic entry or a locked period
- **WHEN** consolidation is requested
- **THEN** the entire operation is rejected without unlocking, cancelling or rewriting financial documents

#### Scenario: M08 Reject cross-company history
- **GIVEN** either card has operational history in another company, including historical records with zero current stock
- **WHEN** consolidation is evaluated for the current company
- **THEN** consolidation is rejected without changing either company's records

#### Scenario: Reject multi-variant templates
- **GIVEN** current-stock consolidation is selected
- **AND** at least one selected card belongs to a template with more than one variant
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and the variant limitation is reported

#### Scenario: Reject incompatible identity and inventory settings
- **GIVEN** current-stock consolidation is selected
- **AND** the selected cards differ in company ownership, product kind, unit-of-measure category, unit of measure, or storage behavior
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and every incompatible setting is reported

#### Scenario: Reject incompatible stock valuation settings
- **GIVEN** current-stock consolidation is selected
- **AND** stock must be transferred and the selected cards do not both use compatible FIFO valuation settings and the same inventory adjustment location
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and the incompatible valuation setting is reported

#### Scenario: Reject tracked products
- **GIVEN** current-stock consolidation is selected
- **AND** at least one selected card uses lot or serial tracking or has lot or serial records
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked without modifying either card

#### Scenario: Reject current stock or reservations
- **GIVEN** current-stock consolidation is selected
- **AND** either selected card has a reserved quantity or current stock that is not eligible for the defined transfer
- **WHEN** the consolidation preview is evaluated or confirmation is attempted
- **THEN** consolidation is blocked and the unsupported stock or reservation is reported

#### Scenario: Accept eligible current stock
- **GIVEN** current-stock consolidation is selected
- **AND** the duplicate has positive stock that satisfies all stock transfer eligibility rules
- **WHEN** the consolidation preview is evaluated
- **THEN** current stock is presented as transferable data instead of a blocker

#### Scenario: Revalidate before confirmation
- **GIVEN** current-stock consolidation is selected
- **AND** an eligible preview has already been generated
- **WHEN** product or operational data changes before confirmation and makes the pair ineligible
- **THEN** confirmation is refused using the current data and no partial consolidation is applied

### Requirement: State-aware reference handling

In current-stock mode, only editable draft references SHALL move, while non-draft operational history SHALL remain on the archived source. For an eligible full-history scope, the system SHALL redirect all supported draft, confirmed, completed and cancelled operational product references to the canonical product as one operation. Related purchase, sales and POS lines, stock movements and movement details MUST agree on product identity. Except for explicitly retired old consolidation transfer pairs, original document identities, lifecycle states, dates, quantities, units, descriptions, prices, discounts, taxes, commercial totals and return relationships SHALL remain unchanged. Protected accounting records SHALL remain outside mutation and SHALL block consolidation when their references prevent a consistent result. Historical evidence from prior corrections and cost operations SHALL remain immutable and resolvable through consolidation audit.

#### Scenario: M09 Transfer completed and cancelled references
- **GIVEN** eligible purchase, sales, POS and stock records reference a duplicate
- **WHEN** full history consolidation completes
- **THEN** every covered operational reference uses the canonical product, including completed and cancelled records
- **AND** document identities, states, dates, entered business values and supported return relationships remain unchanged

#### Scenario: M10 Preserve editable document values
- **WHEN** eligible draft quotations or purchase requests are included in consolidation
- **THEN** their product references change while their entered quantities, descriptions, units, prices, discounts and taxes remain unchanged

#### Scenario: M11 Preserve prior audit evidence
- **GIVEN** supported previous corrections or cost operations refer to records being consolidated
- **WHEN** consolidation completes
- **THEN** their original evidence remains unchanged and can be related to the new operational identity through the merge audit
- **AND** a protected link without such supported handling blocks the merge

#### Scenario: Redirect eligible draft documents
- **GIVEN** current-stock consolidation is selected
- **AND** editable draft sales or purchase documents reference the duplicate card
- **WHEN** consolidation succeeds
- **THEN** their product lines reference the canonical card and retain their entered quantities, units, descriptions, prices, taxes, and discounts

#### Scenario: Preserve non-draft history
- **GIVEN** current-stock consolidation is selected
- **AND** confirmed, completed, cancelled, posted, returned, or otherwise non-editable documents reference the duplicate card
- **WHEN** consolidation succeeds
- **THEN** those references and their business values remain unchanged

#### Scenario: Open historical source product
- **GIVEN** current-stock consolidation is selected
- **AND** a preserved historical document references a consolidated duplicate
- **WHEN** a permitted user opens the referenced product card
- **THEN** the archived card remains accessible and identifies its canonical card

### Requirement: Authorization, audit, and atomicity

Full history consolidation MUST use the existing separate consolidation privilege, company boundaries, a read-only preview and explicit confirmation. Confirmation SHALL disclose that past product reports change and that downstream stored costs require a separate manual recomputation. The entire rewrite, legacy conversion, stock reconciliation, aliases and archival lifecycle SHALL be atomic and protected against stale previews and concurrent changes. Applied operations SHALL retain protected evidence identifying actor, time, source cards, affected records, original identities and retired transfer pairs. Arbitrary API writes MUST NOT bypass these guarantees.

#### Scenario: M12 Reject unauthorized mutation
- **WHEN** an unauthorized user calls confirmation, attempts a direct protected write or supplies a forged internal-operation parameter
- **THEN** access is denied without any business or audit mutation

#### Scenario: M13 Cancel before confirmation
- **WHEN** the user cancels a preview or confirmation
- **THEN** no movement, product reference, quantity, valuation or applied audit record changes

#### Scenario: M14 Reject a stale or competing confirmation
- **GIVEN** relevant source records or their membership have changed after preview, or a competing operation holds the required locks
- **WHEN** confirmation is attempted
- **THEN** it is rejected without partial changes and current data must be reviewed

#### Scenario: M15 Roll back a failed merge
- **GIVEN** a failure occurs after some internal merge steps
- **WHEN** the operation fails
- **THEN** all reference, quantity, state, alias and audit mutations from that attempt are rolled back

#### Scenario: M16 Reuse the applied result
- **WHEN** an applied operation is submitted again
- **THEN** it returns the existing result without repeating the rewrite

#### Scenario: M26 Protect applied evidence
- **WHEN** a user attempts to edit, copy as applied, or delete completed consolidation evidence
- **THEN** the mutation is refused and the original evidence remains available to authorized readers

#### Scenario: M27 Retry after a rolled-back failure
- **GIVEN** an earlier failed attempt was rolled back and its blocking cause has been resolved
- **WHEN** the user reviews and confirms a new attempt
- **THEN** consolidation can complete once from the current data

#### Scenario: Reject an unauthorized user
- **GIVEN** current-stock consolidation is selected
- **WHEN** a user without product-consolidation permission attempts to preview or confirm consolidation through the user interface or server API
- **THEN** access is denied and no product or stock data is changed

#### Scenario: Confirm an irreversible action
- **GIVEN** current-stock consolidation is selected
- **AND** the preview has no blockers and identifies stock to transfer
- **WHEN** the user requests consolidation
- **THEN** the system requires explicit final confirmation that stock will be transferred and the duplicate will be archived

#### Scenario: Cancel before stock transfer
- **GIVEN** current-stock consolidation is selected
- **AND** a stock-aware consolidation preview is open
- **WHEN** the user cancels or closes it without final confirmation
- **THEN** no stock movement, valuation change, product change, or audit record is created

#### Scenario: Record a successful consolidation
- **GIVEN** current-stock consolidation is selected
- **WHEN** stock-aware consolidation succeeds
- **THEN** the canonical card records who performed it, when it occurred, which duplicate was consolidated, and which transfer movements were created

#### Scenario: Roll back a failed consolidation
- **GIVEN** current-stock consolidation is selected
- **AND** validation, stock movement completion, valuation, or any later consolidation write fails
- **WHEN** the operation ends with an error
- **THEN** all changes from that attempt are rolled back, including stock quantities, movement values, configuration, aliases, links, and archival state

#### Scenario: Retry after a failed attempt
- **GIVEN** current-stock consolidation is selected
- **AND** a previous consolidation attempt failed without partial changes
- **WHEN** the blocking cause is resolved and an authorized user retries
- **THEN** the system revalidates current stock and can complete the consolidation once



### Requirement: Current-dated stock transfer

In current-stock consolidation mode, the system SHALL transfer eligible on-hand stock from the duplicate product to the canonical product through completed inventory movements dated at the consolidation time, without changing historical product references or movement dates.

#### Scenario: Preview transferable stock
- **GIVEN** current-stock consolidation is selected
- **AND** the duplicate product has eligible positive stock in valued internal locations
- **WHEN** an authorized user previews consolidation
- **THEN** the preview shows the total quantity and value to transfer
- **AND** the preview identifies the affected locations and remaining FIFO receipt layers

#### Scenario: Consolidate products with positive stock
- **GIVEN** current-stock consolidation is selected
- **AND** the canonical product has 5 units and the duplicate product has 10 eligible units
- **WHEN** consolidation succeeds
- **THEN** the canonical product has 15 units and the duplicate product has zero units
- **AND** the duplicate is archived according to the normal consolidation lifecycle

#### Scenario: Preserve storage dimensions
- **GIVEN** current-stock consolidation is selected
- **AND** eligible duplicate stock is distributed across multiple valued internal locations or packages
- **WHEN** consolidation succeeds
- **THEN** the same quantities of the canonical product are available in the corresponding locations and packages

#### Scenario: Preserve historical stock reports
- **GIVEN** current-stock consolidation is selected
- **AND** the duplicate stock originated from movements completed before consolidation
- **WHEN** consolidation succeeds
- **THEN** the transfer movements are completed at the consolidation time
- **AND** stock reports for times before consolidation remain unchanged

#### Scenario: Consolidate products without stock
- **GIVEN** current-stock consolidation is selected
- **AND** neither selected product has stock or reservations
- **WHEN** consolidation succeeds
- **THEN** the system completes the existing consolidation behavior without creating stock transfer movements


### Requirement: FIFO value preservation

In current-stock consolidation mode, for eligible FIFO products, the system MUST preserve the duplicate product's inventory value at the consolidation time and SHALL create separately auditable canonical receipt layers for the transferred remaining FIFO quantities.

#### Scenario: Preserve multiple remaining FIFO layer values
- **GIVEN** current-stock consolidation is selected
- **AND** the duplicate has remaining quantities from receipts with different unit values
- **WHEN** consolidation succeeds
- **THEN** each transferred canonical receipt layer retains the value proportional to its source remaining quantity
- **AND** the canonical product's inventory value after consolidation equals the sum of both products' inventory values immediately before consolidation, subject only to currency rounding

#### Scenario: Append transferred layers to canonical FIFO
- **GIVEN** current-stock consolidation is selected
- **AND** the canonical product already has positive FIFO stock
- **WHEN** duplicate stock is transferred
- **THEN** the transferred receipt layers follow the canonical product's pre-existing layers in future FIFO valuation order

#### Scenario: Record source receipt audit data
- **GIVEN** current-stock consolidation is selected
- **WHEN** a transferred canonical receipt layer is created
- **THEN** authorized users can identify its source receipt, original receipt date, duplicate product, transferred quantity, and transferred value
- **AND** the recorded original receipt date does not act as the completion date of the new movement

#### Scenario: Warn about mutable source valuation
- **GIVEN** current-stock consolidation is selected
- **AND** a remaining source receipt can still be affected by unposted or partial supplier billing
- **WHEN** consolidation is previewed
- **THEN** the preview warns that the transferred value is a snapshot taken at confirmation and later source valuation changes will not be synchronized automatically


### Requirement: Stock transfer eligibility

In current-stock consolidation mode, the system MUST transfer only unreserved, non-negative, company-owned stock whose quantity and FIFO value can be reconciled before confirmation.

#### Scenario: Reject negative or unreconciled stock
- **GIVEN** current-stock consolidation is selected
- **AND** the duplicate has a negative internal quantity or its transferable quantity cannot be reconciled with its remaining FIFO quantities
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked and the inconsistency is reported

#### Scenario: Reject stock under inventory counting
- **GIVEN** current-stock consolidation is selected
- **AND** an unfinished inventory count exists for either selected product
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked without applying a partial transfer

#### Scenario: Reject open duplicate stock operations
- **GIVEN** current-stock consolidation is selected
- **AND** a non-cancelled, non-completed stock movement references the duplicate product
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked until the movement is completed or cancelled

#### Scenario: Reject unsupported ownership or tracking
- **GIVEN** current-stock consolidation is selected
- **AND** transferable duplicate stock belongs to another owner or either selected product uses lot or serial tracking
- **WHEN** consolidation is previewed or confirmed
- **THEN** consolidation is blocked and the unsupported stock dimension is reported

#### Scenario: Revalidate stock before confirmation
- **GIVEN** current-stock consolidation is selected
- **AND** an eligible preview was generated
- **WHEN** quantities, reservations, FIFO values, or open movements change before confirmation
- **THEN** confirmation uses current data and refuses any now-ineligible transfer without partial consolidation

## ADDED Requirements

### Requirement: Unified original stock history

Full-history consolidation SHALL establish one canonical operational history using the original movements and receipt chronology. It MUST NOT create replacement receipts, opening balances or current-dated transfer movements. Current stock by company, location, package and ownership dimensions SHALL equal the combined pre-merge physical stock, with zero residual stock on absorbed sources. Original real receipt quantities and values SHALL remain unchanged. Historical stock reports SHALL attribute absorbed history to the canonical product. Stored downstream issue and POS costs SHALL remain unchanged during consolidation; standard FIFO may produce different costs from the merged receipt sequence when manually recomputed.

#### Scenario: M17 Combine original receipts
- **GIVEN** the canonical product received 20 units and its duplicate received 100 units on August 28 before any consumption
- **WHEN** their histories are consolidated
- **THEN** canonical historical availability before subsequent consumption is 120 units
- **AND** both original receipts retain their dates, quantities and values without a new receipt

#### Scenario: M18 Reconcile physical stock
- **GIVEN** eligible source stock is held in supported locations and packages
- **WHEN** consolidation completes
- **THEN** canonical stock in each dimension equals the combined pre-merge stock and absorbed source stock is zero
- **AND** any mismatch aborts the operation

#### Scenario: M19 Keep recomputation manual
- **WHEN** consolidation completes
- **THEN** existing real issue values and POS costs are not automatically recalculated
- **AND** no pending-recomputation marker is created

#### Scenario: M20 Merge another duplicate later
- **GIVEN** a canonical card has fully absorbed one duplicate
- **WHEN** another eligible duplicate is consolidated into it
- **THEN** its history joins the same canonical timeline and all earlier aliases and merge evidence remain available

#### Scenario: M28 Consolidate compatible cards without stock history
- **GIVEN** compatible cards have no stock history and satisfy the existing configuration-only eligibility rules
- **WHEN** consolidation completes
- **THEN** supported configuration and editable references transfer with aliases and archival audit, without requiring stock or FIFO settings for non-stocked products

#### Scenario: M21 Preserve ordinary behavior
- **WHEN** users process products without invoking consolidation
- **THEN** standard stock operations, valuation, product editing protections and identifier resolution retain their existing behavior

### Requirement: Conversion of previous stock-only consolidations

The system SHALL provide an explicit reviewed conversion for existing canonical cards and their archived sources. Conversion MUST identify all old consolidation transfer pairs from verifiable evidence and retire their operational quantity and valuation effects while retaining inspectable original evidence. It SHALL move the real source history to the canonical card without reactivating sources or duplicating aliases. No old pair SHALL remain an active FIFO receipt after conversion. Installation and upgrade MUST NOT convert business history automatically.

#### Scenario: M22 Convert an existing transfer
- **GIVEN** a duplicate received 100 units, sold 4, and transferred the remaining 96 through an old consolidation pair
- **WHEN** the full group is converted
- **THEN** the original receipt and sales belong to the canonical product and the 96-unit pair has no active stock or valuation effect
- **AND** original pair evidence remains inspectable

#### Scenario: M23 Reject an unproven old transfer
- **GIVEN** an old transfer has missing, inconsistent or protected links or cannot be reconciled with the recorded consolidation
- **WHEN** conversion is previewed or confirmed
- **THEN** the entire conversion is rejected with the affected pair identified
- **AND** ordinary movements are not inferred to be consolidation pairs from a name or date alone

#### Scenario: M24 Upgrade without rewriting history
- **WHEN** the module is installed or upgraded
- **THEN** existing product references and old completed transfers remain unchanged until a user confirms conversion
- **AND** both consolidation modes remain available, with full-history conversion requiring explicit selection

#### Scenario: M29 Add a stock-only source after full consolidation
- **GIVEN** a canonical card has previously completed full-history consolidation
- **WHEN** another duplicate is merged into it using current-stock mode
- **THEN** the new duplicate retains its historical records under the current-stock rules
- **AND** the group is no longer treated as fully unified for historical consumption until that source is explicitly converted

#### Scenario: M25 Convert all old sources of one target
- **GIVEN** a canonical card has absorbed several sources using the old behavior
- **WHEN** conversion is requested for one of those sources
- **THEN** preview and application cover every unconverted source of that target atomically
- **AND** an ineligible source blocks the group rather than leaving a partly unified history
