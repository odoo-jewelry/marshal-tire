## Purpose

Repair provably incorrect zero-valued historical POS stock issues and recompute the affected POS costs through one reviewed and auditable operation.

## ADDED Requirements

### Requirement: Explicit stock repair mode

The operation SHALL offer a separate, disabled-by-default stock-repair mode. It SHALL identify the action as an authorized change to historical stock valuation, including where the costing method changed after the sale. Ordinary recomputation SHALL retain its existing behavior and permissions.

#### Scenario: R01 Choose stock repair explicitly
- **WHEN** a manager creates a cost-recomputation operation
- **THEN** stock repair is disabled until explicitly selected
- **AND** enabling it identifies that historical stock values may change

#### Scenario: R02 Preserve nonzero stock values
- **WHEN** stock repair encounters an otherwise supported issue with a nonzero valuation
- **THEN** that valuation is not replaced
- **AND** independently eligible POS costs can still be recomputed from it

### Requirement: Provable receipt basis

Repair SHALL be limited to zero-valued completed outgoing movements directly attributable to completed sales in closed sessions, for currently FIFO-valued, untracked, company-owned products under periodic valuation. A strictly earlier completed supplier receipt in the same company, product unit and storage location MUST be the sole eligible receipt before the issue. Its positive finite quantity and current positive finite valuation, less intervening proven outgoing quantities, MUST support the entire issue. Historical quantities MUST reconcile without negative stock, ownership changes, unexplained adjustments or internal transfers. Multiple earlier receipts or ambiguous ordering SHALL require review instead of constructing a new historical FIFO engine. Later receipts and current product-card costs MUST NOT supply the repaired amount. The operation MUST inspect the complete relevant stock history without a fixed movement-count limit or silent truncation.

#### Scenario: R03 Repair an issue against its sole earlier receipt
- **GIVEN** one unit was received at a recorded value of 284.01 before a one-unit zero-valued sale issue and all eligibility conditions hold
- **WHEN** stock repair is previewed
- **THEN** the proposed issue value is 284.01 and identifies that receipt

#### Scenario: R04 Ignore a more expensive later receipt
- **GIVEN** the eligible earlier receipt valued a unit at 284.01 and a later receipt values another unit at 900
- **WHEN** the older sale issue is previewed and repaired
- **THEN** its repaired value is 284.01, not 900

#### Scenario: R05 Account for earlier consumption
- **GIVEN** the sole receipt contained four units and earlier completed issues consumed three
- **WHEN** a two-unit zero-valued issue is evaluated
- **THEN** repair is refused because the proven remaining quantity is insufficient

#### Scenario: R06 Reject an ambiguous or invalid source
- **WHEN** the history contains multiple earlier receipts, indistinguishable receipt/issue timestamps, an unexplained adjustment, negative stock, unsupported storage changes or no positive finite receipt value
- **THEN** the affected issue is excluded with a specific explanation and no product-cost fallback

#### Scenario: R07 Require complete POS coverage of an issue
- **GIVEN** a candidate issue also supplies POS lines outside the frozen selection or belongs to an aggregate session source
- **WHEN** stock repair is previewed
- **THEN** that issue is excluded without silently adding related lines or changing their source value

#### Scenario: R39 Inspect history exceeding the former movement limit
- **GIVEN** an otherwise eligible issue has more than 10000 movements in the relevant product and company history
- **WHEN** the manager previews and applies its stock repair
- **THEN** the complete history is checked and the eligible reviewed repair is applied
- **AND** history size alone does not cause rejection or truncation

### Requirement: Financial and lifecycle boundaries

Repair SHALL reject issues with linked accounting or analytic entries, invoiced POS orders, affected locked periods, perpetual valuation, or unresolved evidence of financial impact. It SHALL reject returns, correction chains, consolidated products, kits, combo structures, tracked or consigned stock and incomplete deliveries. These exclusions SHALL be enforced again at application. Unsupported cases SHALL remain visible for separate review; this operation SHALL NOT create compensating accounting or stock movements.

#### Scenario: R08 Reject financial dependencies
- **WHEN** an issue has linked accounting or analytic entries, its order is invoiced, its period is locked or its product uses perpetual valuation
- **THEN** stock repair is unavailable for it and the financial dependency is explained

#### Scenario: R09 Reject dependent or unsupported stock history
- **WHEN** a candidate has a non-cancelled return, a project correction or consolidation link, tracking, consignment, an unsupported product structure or incomplete delivery
- **THEN** it is excluded without changing any related document

#### Scenario: R10 Explain a costing-method change
- **GIVEN** a zero-valued sale was completed under Standard Price and its product now uses FIFO
- **WHEN** a supported repair is previewed
- **THEN** the preview states that it proposes a receipt-based correction to historical valuation, not restoration of proof that FIFO applied at the sale date

### Requirement: Reviewed stock and POS consequences

Preview SHALL perform no stock, product-cost, accounting or POS-cost writes. It SHALL show each distinct issue once with quantity, company currency, previous and proposed stock value, receipt evidence and linked selected POS lines. It SHALL show the corresponding POS cost and margin differences using the existing company and order-date currency rules. Application MUST require a reason and a separate acknowledgement of historical stock-value changes; the existing zero-source acknowledgement SHALL NOT authorize stock repair. The receipt value SHALL be explicitly described as the current evidence snapshot, including warnings when unposted or partial supplier billing may change it later.

#### Scenario: R11 Preview without operational effects
- **WHEN** the manager previews stock repair
- **THEN** old and proposed stock and POS amounts are visible without changing any operational amount or creating valuation-adjustment history

#### Scenario: R12 Review totals and currencies
- **GIVEN** eligible one-unit issues have proposed company-currency values of 284.01, 491.75 and 38.70
- **WHEN** the operation is previewed
- **THEN** the stock repair total is 814.46 without double-counting shared selected lines
- **AND** POS amounts are converted at their order dates and displayed separately by currency

#### Scenario: R13 Require stock-specific acknowledgement
- **WHEN** a repair is applied without a reason or without acknowledging the historical stock-value changes
- **THEN** the whole application is rejected even if zero-source acknowledgement was given

#### Scenario: R14 Warn about unsettled receipt valuation
- **GIVEN** the eligible receipt is not fully covered by posted supplier billing
- **WHEN** its value is proposed as repair evidence
- **THEN** the preview warns that the amount is a snapshot and later valuation changes will not automatically update the repaired issue

### Requirement: Atomic fixed-value application and history

The operation MUST revalidate and lock the reviewed issues, receipt evidence, quantities, financial eligibility and affected POS records before applying fixed reviewed stock values. It MUST recompute the selected POS costs from those repaired values and record both results in one transaction. An unexpected failure SHALL undo every stock, POS and history change from the operation. Historical quantities, movement dates and storage dimensions SHALL remain unchanged. History SHALL retain receipt evidence, old/new stock and POS values, author, time and reason, and SHALL be protected from ordinary editing, deletion, duplication and forged direct requests. A later standard operation MUST NOT silently replace a repaired value with a cost from today's FIFO stock; intentional reversal or revaluation requires a separate traceable workflow outside this version.

#### Scenario: R15 Reject changed evidence
- **GIVEN** a preview exists
- **WHEN** receipt valuation, historical movement membership, quantities, product settings, exchange rates, selected costs, return links or financial dependencies change before application
- **THEN** the complete preview is rejected as stale before operational writes

#### Scenario: R16 Roll back a stock repair followed by POS failure
- **WHEN** the first issue has been repaired and a later required stock or POS write fails
- **THEN** all issue values, POS costs and applied-history changes from that operation are rolled back

#### Scenario: R17 Protect the audit evidence
- **WHEN** a user tries to forge an applied valuation result, modify receipt evidence or delete the history of a successful repair through editing, import or a direct request
- **THEN** the operation is refused without altering the repaired records

#### Scenario: R18 Preserve the reviewed amount on later valuation calls
- **GIVEN** an issue was repaired to 284.01 and later stock has unit cost 900
- **WHEN** a standard recalculation encounters the repaired issue
- **THEN** it preserves the documented 284.01 or explicitly refuses an incompatible change instead of silently substituting 900

#### Scenario: R19 Serialize overlapping repairs
- **GIVEN** two operations preview the same zero-valued issue
- **WHEN** their applications overlap
- **THEN** at most one repairs it and the other receives a busy or stale-preview response without a second valuation adjustment

#### Scenario: R25 Return goods after a completed repair
- **GIVEN** an issue was successfully repaired and a customer subsequently makes an otherwise valid ordinary return
- **WHEN** the standard return is processed
- **THEN** it uses the repaired original stock value under standard return rules and retains the repair history

### Requirement: Permissions and safe introduction

Stock repair SHALL require POS-manager and stock-manager permissions plus ordinary access to every affected record and source. All evidence, locks, amounts and history SHALL remain company-isolated. Installation and upgrade SHALL default existing operations to ordinary recomputation, preserve old previews and history, and SHALL NOT repair any stock value automatically. Copies SHALL contain fresh criteria only and require new review and acknowledgement. An independently ineligible repair MAY be skipped only when that exclusion was explicitly reviewed; no new runtime skips are allowed.

#### Scenario: R20 Deny a POS manager without stock permission
- **WHEN** a POS manager lacking stock-manager permission requests repair preview or application directly
- **THEN** stock repair is denied while ordinary POS recomputation remains available subject to its existing access checks

#### Scenario: R21 Reject cross-company evidence
- **WHEN** a repair includes an issue, receipt or linked record from an unauthorized or different company
- **THEN** it is rejected without exposing that company's amounts or changing records

#### Scenario: R22 Upgrade safely
- **WHEN** the module is upgraded with existing draft, reviewed and applied operations
- **THEN** existing historical values and ordinary operation behavior remain unchanged and no stock repair is enabled automatically

#### Scenario: R27 Copy repair criteria without applied effects
- **WHEN** an operation containing stock repair is copied
- **THEN** the copy contains only fresh criteria without results or acknowledgement and requires a new preview

#### Scenario: R23 Keep later receipt changes explicit
- **WHEN** a receipt valuation changes after a completed repair
- **THEN** the repair history retains its original evidence and neither its issue value nor its POS cost changes automatically

#### Scenario: R24 Apply a reviewed mixed selection
- **GIVEN** preview includes a supported stock repair, a normal POS-only recomputation and an explicitly excluded issue
- **WHEN** the operation is confirmed with the required permissions and acknowledgements
- **THEN** the two supported results are applied atomically, the excluded issue and its POS costs remain unchanged, and the counts distinguish repaired issues from recomputed and skipped POS lines

#### Scenario: R26 Preserve evidence on module removal
- **WHEN** removal of the module is requested while applied stock repairs exist
- **THEN** removal is refused before deleting repair evidence or disabling protection of the repaired values
