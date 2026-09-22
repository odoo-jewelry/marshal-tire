## Purpose

Correct selected purchase prices by including their previously excluded taxes and consistently recompute receipt, historical stock and POS costs, with two-decimal price rounding and no separate permanent correction journal.

## ADDED Requirements

### Requirement: Explicit temporary purchase action

Authorized users SHALL be able to invoke a clearly named tax-inclusion and cost-recomputation action from selected purchase orders. A temporary dialog SHALL offer application or cancellation without requiring a reason, a saved preview or a separate review stage. Opening or cancelling the dialog MUST NOT change business data. Application SHALL use current server-validated records rather than accepting proposed prices or costs supplied by the caller.

#### Scenario: P01 Open the action for selected purchases
- **WHEN** an authorized user opens the action for selected purchase orders
- **THEN** a temporary dialog identifies the selected purchases and offers application or cancellation
- **AND** no purchase price, stock value or POS cost changes before application

#### Scenario: P02 Cancel before application
- **WHEN** the user closes or cancels the temporary dialog
- **THEN** all business data remains unchanged and the purchases remain available for a later application

### Requirement: Include supported taxes with two-decimal rounding

For each eligible purchase line carrying positive excluded percentage taxes, the operation SHALL calculate the tax-inclusive undiscounted unit price using the standard tax calculation, round that unit price HALF-UP to exactly two decimal places, and remove the line's taxes. The existing discount SHALL remain unchanged and continue to apply to the corrected unit price. Standard tax ordering and supported tax-on-tax effects MUST be respected. Existing configured price precision SHALL remain two decimal places; differing configuration SHALL cause an explained refusal rather than an implicit configuration change. The resulting difference in order totals caused by rounding SHALL be accepted. Lines without taxes or with only zero percentage taxes SHALL remain unchanged. An entire selection containing no prices to correct SHALL complete without valuation changes. Fixed, included, negative or otherwise unsupported tax definitions SHALL cause rejection of the complete selection.

#### Scenario: P03 Include excluded percentage taxes
- **GIVEN** an eligible undiscounted unit price is 100 with an excluded 20 percent tax
- **WHEN** the operation is applied
- **THEN** its unit price becomes 120 and its line taxes are empty
- **AND** an eligible combination of percentage taxes follows the standard tax order and tax-base rules

#### Scenario: P04 Round prices without changing configured precision
- **GIVEN** an eligible unit price is 27.33 with an excluded 20 percent tax and configured price precision is two decimal places
- **WHEN** the operation is applied
- **THEN** the resulting 32.796 unit price is stored as 32.80 and configured price precision remains unchanged
- **AND** an exact half-cent result rounds up rather than to the nearest even cent

#### Scenario: P05 Preserve the existing discount
- **GIVEN** an eligible line has an undiscounted unit price of 100, a 10 percent discount and an excluded 20 percent tax
- **WHEN** the operation is applied
- **THEN** the undiscounted unit price becomes 120, the discount remains 10 percent and the discounted tax-free unit amount becomes 108

#### Scenario: P06 Leave absent and zero-only taxes unchanged
- **GIVEN** every selected purchase line has either no taxes or only zero percentage taxes
- **WHEN** the operation is applied
- **THEN** prices and taxes remain unchanged, no stock or POS costs are recomputed, and the result reports that nothing required correction

#### Scenario: P07 Reject unsupported tax or precision settings
- **GIVEN** a selected line has a fixed, included, negative or otherwise unsupported tax, or configured price precision differs from two decimal places
- **WHEN** application is requested
- **THEN** the whole selection is rejected with the incompatible setting identified and no partial price or valuation changes

### Requirement: Supported documents and valuation boundaries

The operation SHALL accept a nonempty selection of confirmed, unlocked, fully received purchase orders from one authorized company, using that company's currency. Corrected product lines SHALL have positive finite prices and quantities and a discount from zero inclusive to 100 percent exclusive. Its supported scope SHALL be company-owned goods without lot or serial tracking under FIFO and periodic valuation, with direct receipts, outgoing customer deliveries and linked customer returns through one stock location per affected product. Disabled inventory tracking alone MUST NOT reject goods whose complete actual movement history reconciles with their recorded internal quantity. Services, advance-payment lines and price-only correction without the required historical evidence SHALL remain unsupported. The operation MUST NOT change the inventory-tracking setting or create quantities to obtain eligibility. Quantities SHALL use the product's base unit. Incomplete or complex stock flows, supplier returns, absorbed product cards, incomplete consolidation, active synthetic consolidation movements and unresolved ownership or valuation evidence SHALL be rejected. Proven fully consolidated canonical history and eligible completed historical stock write-offs SHALL be supported under the conditions of purchase-cost-recompute-integrated-history; their origin alone MUST NOT cause refusal. Existing manually adjusted stock values, protected previous cost corrections, protected historical stock write-offs, stock-related accounting or analytic entries and affected locked or closed valuation periods MUST cause an explained atomic refusal. Any non-cancelled supplier bill linked to a selected purchase line, including a draft bill, SHALL prevent correction. Ordinary POS session revenue accounting alone MUST NOT prevent correction when all stock and POS eligibility conditions are satisfied; such accounting SHALL remain unchanged.

#### Scenario: P08 Reject an ineligible purchase selection
- **WHEN** application is requested for an empty selection, an unconfirmed, locked or cancelled purchase, a purchase that is not fully received, a purchase in a different currency from its company, or an invalid price, quantity or discount
- **THEN** the complete request is rejected with the relevant document or selection condition identified

#### Scenario: P09 Reject unsupported stock history
- **GIVEN** affected history uses lot or serial tracking, third-party ownership, non-FIFO costing, perpetual valuation, multiple stock locations for one product, non-base units, incomplete movements, supplier returns, complex transfers, an absorbed product card, incomplete consolidation or active synthetic consolidation movements
- **WHEN** application is requested
- **THEN** the complete selection is rejected with the affected product and unsupported condition identified

#### Scenario: P10 Preserve protected valuation and financial history
- **GIVEN** a selected purchase line has a non-cancelled supplier bill, including a draft bill, or required correction would affect a manually adjusted value, a protected previous cost correction, a historical write-off that fails the integrated-history eligibility rules, stock-related accounting or analytic entries, or a locked or closed valuation period
- **WHEN** application is requested
- **THEN** the entire selection is rejected with the protected dependency identified
- **AND** no protection is bypassed and no compensating stock or accounting entry is created

### Requirement: Complete historical receipt and cost recomputation

For each product whose purchase lines are converted, the operation SHALL revalue its affected completed receipts from the corrected purchase terms and recompute every supported downstream outgoing value and linked customer return through the time of application, even if two-decimal rounding leaves a converted unit price numerically unchanged. Earlier history SHALL be inspected as evidence without rewriting unaffected earlier values. Unselected later purchase receipts SHALL retain their own recorded values and participate in chronological FIFO normally. No fixed history-size limit, silent truncation or incomplete affected selection SHALL be allowed. Customer returns SHALL derive their cost proportionally from their original outgoing movement, using its corrected value when that issue is inside the correction interval or its unchanged recorded value when it precedes that interval, and become available for subsequent FIFO consumption. Eligible historical write-offs SHALL participate in the same outgoing chronology through valuation-only updates, preserving their completed physical facts and original preparation evidence. All affected returns MUST have a provable original issue in the same company, product and location; cumulative returned quantity MUST NOT exceed its original quantity. Current stock valuation and product cost SHALL be consistent with the completed recomputation, including products with no subsequent POS sale.

#### Scenario: P11 Recompute the complete downstream history
- **GIVEN** a corrected purchase receipt is followed by several supported issues and another purchase receipt at a different price
- **WHEN** the operation is applied
- **THEN** every affected issue is valued from the chronological FIFO sequence including the unchanged later receipt
- **AND** affected history beyond the initially selected documents is included without movement-count truncation

#### Scenario: P12 Correct a purchase without subsequent POS sales
- **GIVEN** an eligible purchase has remaining stock and no subsequent POS sale
- **WHEN** the operation is applied
- **THEN** its receipt value, current remaining stock valuation and product cost reflect the corrected purchase price without requiring a POS record

#### Scenario: P13 Recompute a negative-stock sale and its return chain
- **GIVEN** two units were received at a corrected unit cost of 120, followed by an issue of 150 units, its linked return of 150 units and a later issue of one unit
- **WHEN** the operation is applied
- **THEN** the first issue and its return are each valued at 18000, the later issue is valued at 120 and the remaining one unit is valued at 120
- **AND** the original quantities and chronological movement identities remain unchanged

#### Scenario: P14 Value a partial linked return
- **GIVEN** an original issue of three units has a corrected total cost of 90 and its linked customer return contains one unit
- **WHEN** the operation is applied
- **THEN** the return is valued at 30 and that returned quantity contributes to subsequent FIFO at that value

#### Scenario: P15 Reject an unprovable customer return
- **GIVEN** an affected customer return lacks a valid original issue, precedes that issue, crosses product, company or location boundaries, or makes cumulative returns exceed the original issue quantity
- **WHEN** application is requested
- **THEN** the whole selection is rejected without guessing a return cost or partially changing the original issue

#### Scenario: P34 Preserve an earlier original issue used by a later return
- **GIVEN** a customer return occurs after the corrected receipt but its original issue predates the correction interval and has a recorded unit cost of 90
- **WHEN** the operation recomputes the return
- **THEN** the return uses the original recorded unit cost of 90
- **AND** the earlier issue and its POS cost remain unchanged

### Requirement: Historical evidence for shortages and equal timestamps

An existing negative quantity in recorded history MAY be recomputed without inventing receipt quantities. If an issue exhausts a nonempty historical FIFO balance, its uncovered quantity SHALL use the last consumed historical unit cost under standard FIFO shortage semantics. If its pre-issue FIFO balance is empty or negative, the whole issue SHALL use the unit value of the last proven eligible incoming movement strictly preceding its timestamp, including a supported linked customer return. Absence of such evidence SHALL cause refusal. This explicit last-incoming rule MUST NOT be represented as restoration of an unknown historical product-card cost. Future receipts and today's product cost MUST NOT supply or change an earlier issue's value. Issues sharing a timestamp SHALL consume available history once in a deterministic existing-record order. A timestamp mixing incoming and outgoing movements for the same product SHALL be rejected as ambiguous.

#### Scenario: P16 Use proven prior cost when the FIFO balance is exhausted
- **GIVEN** a product's earlier receipt had unit cost 120, previous issues exhausted its stock and a later issue has no available FIFO quantity
- **WHEN** the operation recomputes that later issue
- **THEN** it uses 120 per unit from the proven prior receipt without inventing stock quantities

#### Scenario: P17 Reject a shortage without prior valuation evidence
- **GIVEN** a historical issue has no available FIFO quantity and no proven prior eligible incoming value
- **WHEN** application is requested
- **THEN** the whole operation is refused with the missing historical basis identified, even if a later receipt or current product cost exists

#### Scenario: P18 Exclude future and current costs from historical expenses
- **GIVEN** an earlier supported sale and linked return have a corrected historical unit cost of 120, a later receipt costs 900 and the current product cost is different again
- **WHEN** the operation recomputes the earlier sale and return
- **THEN** both retain the cost derived from 120, independently of the later receipt and current product cost

#### Scenario: P19 Recompute issues sharing one timestamp
- **GIVEN** two supported outgoing movements share a timestamp and their FIFO evidence contains receipts at different earlier unit costs
- **WHEN** the operation is applied
- **THEN** the movements consume that evidence once in deterministic existing-record order and receive the corresponding sequential FIFO costs

#### Scenario: P20 Reject mixed directions at one timestamp
- **GIVEN** an incoming movement and an outgoing movement for the same product share a timestamp
- **WHEN** application is requested
- **THEN** the whole operation is rejected as chronologically ambiguous without assigning an arbitrary earlier date or using the incoming value for the issue

### Requirement: POS costs from corrected stock sources

After stock values have been corrected, the operation SHALL update every affected supported paid or completed POS line, including linked refunds, using its existing completed stock sources, signed quantity and standard order-date currency conversion. Direct order sources SHALL be supported even while the POS session remains open. A shared session source SHALL be supported only in a closed session with complete and provable same-direction attribution; all affected lines sharing the source SHALL be included. Missing or unfinished stock sources, ambiguous mixed directions, protected cost-of-goods-sold entries for affected products in related customer financial documents or their reversals, special deferred-delivery substitutions, project correction chains, kits and combo structures SHALL cause rejection rather than partial recalculation. Invoice presence alone MUST NOT cause rejection, as required by purchase-cost-recompute-invoiced-pos. Existing formulas SHALL make saved POS costs and margins consistent with the corrected sources. Historical preparation source documents MUST be excluded from ordinary POS cost updates; their state, lines and saved costs SHALL remain unchanged, as required by purchase-cost-recompute-integrated-history. The operation MUST NOT close or reopen a session or modify its accounting entries.

#### Scenario: P21 Recompute paid direct-source sales and refunds in an open session
- **GIVEN** affected paid sales and their linked refunds have completed direct stock sources and their session is still open
- **WHEN** the operation is applied
- **THEN** their signed POS costs reflect the corrected stock values and their margins update accordingly
- **AND** the session remains open with its sales, payments and accounting information unchanged

#### Scenario: P22 Recompute a provable closed-session source
- **GIVEN** affected POS lines share a complete, same-direction stock source in a closed session with ordinary revenue accounting
- **WHEN** the operation is applied
- **THEN** every affected line sharing that source receives the standard source-weighted cost, including lines outside the initially selected purchases
- **AND** the session's existing revenue accounting is unchanged and does not itself prevent recomputation

#### Scenario: P23 Reject unsupported POS dependencies
- **GIVEN** an affected POS line has an ambiguous or unfinished stock source, an open shared-session source, protected cost-of-goods-sold entries for its product in a related customer financial document or reversal, an unsupported deferred-delivery cost substitution, a project correction chain, a kit or a combo structure
- **WHEN** application is requested
- **THEN** the complete purchase correction is rejected with the unsupported dependency identified
- **AND** no purchase, stock or POS amounts are partially changed

### Requirement: Atomic application, serialization and repeatability

The complete selected correction SHALL execute atomically from current authorized facts. All required purchase, stock, product-cost and POS updates MUST succeed together; any failure SHALL roll back the entire attempt. Concurrent purchase changes, stock processing, POS processing or competing cost correction MUST NOT produce a mixed or stale result. A conflicting request SHALL either use a fully consistent current state or fail with an actionable retry response. Repeating a successful request SHALL not add taxes or costs again; already corrected tax-free purchases SHALL result in no further changes. Application SHALL report the actual counts of corrected purchase lines, revalued receipts, issues, returns and POS lines, together with the actual purchase-total difference caused by rounding. Quantities, movement identities and dates, document states, payments, sales prices, revenue, accounting entries and current supplier pricelist values SHALL remain unchanged.

#### Scenario: P24 Report actual results and preserve unrelated business values
- **WHEN** an eligible correction completes
- **THEN** the result shows the actual processed-record counts and actual purchase-total rounding difference
- **AND** quantities, movement identities and dates, document states, payments, sales prices, revenue, accounting entries and current supplier pricelist values remain unchanged

#### Scenario: P25 Roll back a late failure
- **GIVEN** receipt and issue values have already been changed within the attempted operation
- **WHEN** a later required return, product-cost or POS update fails
- **THEN** all changes from the attempt, including purchase prices and taxes, are rolled back and no successful result is reported

#### Scenario: P26 Handle concurrent changes consistently
- **WHEN** another request concurrently changes an affected purchase or valuation source, adds stock or POS history, or applies an overlapping correction
- **THEN** the correction either completes against one consistent current history or fails with an actionable retry response
- **AND** no stale or partially mixed valuation is committed

#### Scenario: P27 Retry a successful correction without increasing prices again
- **GIVEN** the selected purchases were successfully corrected and their former positive taxes are now absent
- **WHEN** the same operation is requested again
- **THEN** no further tax amount is added, no cost drift occurs and the result reports that nothing required correction

### Requirement: Authorization, visibility and company isolation

Opening and applying the operation SHALL require purchase-manager and stock-manager permissions, normal write access to all changed purchase, stock and product records, and write access to affected POS records. Complete read access to the relevant source history SHALL be required. Changing an eligible historical write-off value SHALL additionally require the existing historical-operation permission; fully consolidated products without affected historical write-offs SHALL NOT require that additional permission. The same authorization and validation MUST apply to direct requests as to the interface. A request SHALL operate in exactly one authorized company; another selected or contextual company MUST NOT contribute its stock, prices or costs. Missing access SHALL cause refusal without disclosing hidden amounts.

#### Scenario: P28 Enforce permissions on direct requests
- **WHEN** a caller lacks either required manager permission or normal write access to a record that would change and invokes the action directly
- **THEN** access is denied without price, tax, stock or POS changes
- **AND** caller-supplied resulting prices or costs cannot bypass server validation

#### Scenario: P29 Require complete company-specific visibility
- **WHEN** the selection mixes companies, references an unauthorized company or requires history that the caller cannot fully read
- **THEN** the request is rejected without revealing hidden source amounts

#### Scenario: P33 Isolate the cost of a shared product
- **GIVEN** the caller can access two companies and a shared product has a later receipt at a different price in the other company
- **WHEN** an eligible correction runs in one company
- **THEN** historical expenses and current product cost use only that company's incoming values, including when its current stock is zero or negative
- **AND** the other company's quantities and costs remain unchanged

### Requirement: No separate journal and unchanged ordinary workflows

The operation MUST NOT create a separate permanent correction journal, mandatory reason, saved review workflow or persistent recomputation history. Existing standard document metadata MAY remain, and existing protected audit records MUST be preserved. Installation and upgrade SHALL NOT change historical business values or run the correction. Ordinary purchasing, inventory, POS processing and existing cost tools SHALL retain their behavior, permissions and protection rules when this explicit action is not used.

#### Scenario: P30 Complete without a separate permanent journal
- **WHEN** an eligible correction completes
- **THEN** its updated business values and completion summary are available without a separate permanent correction record, mandatory reason or saved review stage
- **AND** existing protected audit history is neither changed nor deleted

#### Scenario: P31 Install or upgrade without recalculating history
- **WHEN** the capability is installed or upgraded on a database with existing purchases, movements and POS orders
- **THEN** no purchase price, tax, historical stock value or POS cost is corrected automatically

#### Scenario: P32 Preserve ordinary operations and existing cost tools
- **WHEN** users process purchases, stock, sales, refunds or session closure, or invoke an existing cost tool without using the new action
- **THEN** those operations retain their existing behavior, permissions and protected-history restrictions
