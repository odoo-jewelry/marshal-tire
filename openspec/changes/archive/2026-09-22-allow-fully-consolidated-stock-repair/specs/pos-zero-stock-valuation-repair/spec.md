## MODIFIED Requirements

### Requirement: Financial and lifecycle boundaries

Repair SHALL reject issues with linked accounting or analytic entries, invoiced POS orders, affected locked periods, perpetual valuation, or unresolved evidence of financial impact. It SHALL reject returns, correction chains, incompletely consolidated products, absorbed source cards, kits, combo structures, tracked or consigned stock and incomplete deliveries. A canonical product with proven complete full-history consolidation in the operation company SHALL be evaluated under the same receipt, financial and lifecycle conditions as an ordinary product; consolidation alone MUST NOT exclude it. These exclusions SHALL be enforced again at application. Unsupported cases SHALL remain visible for separate review; this operation SHALL NOT create compensating accounting or stock movements.

#### Scenario: R08 Reject financial dependencies
- **WHEN** an issue has linked accounting or analytic entries, its order is invoiced, its period is locked or its product uses perpetual valuation
- **THEN** stock repair is unavailable for it and the financial dependency is explained

#### Scenario: R09 Reject dependent or unsupported stock history
- **WHEN** a candidate has a non-cancelled return, a project correction, an incomplete consolidation or absorbed-source relationship, tracking, consignment, an unsupported product structure or incomplete delivery
- **THEN** it is excluded without changing any related document

#### Scenario: R10 Explain a costing-method change
- **GIVEN** a zero-valued sale was completed under Standard Price and its product now uses FIFO
- **WHEN** a supported repair is previewed
- **THEN** the preview states that it proposes a receipt-based correction to historical valuation, not restoration of proof that FIFO applied at the sale date

## ADDED Requirements

### Requirement: Proven full-history eligibility for ordinary stock repair

Before preview and again before application, the system SHALL establish that the canonical product has applied full-history consolidation evidence covering every absorbed source in the operation company and that no absorbed source retains non-cancelled stock movements or nonzero stock quantities. Archived sources MUST be included. Absence of proof SHALL retain exclusion with an explanation that full-history conversion is required; an absorbed source SHALL identify its canonical product as the place to continue. The consolidation subsystem SHALL remain optional for ordinary stock repair, and unavailable proof MUST NOT be treated as approval. Cancelled transfer pairs retired by a proven full-history conversion SHALL NOT contribute receipt quantities or values. Active consolidation transfers MUST remain subject to existing rejection. All other stock-repair restrictions and frozen-selection semantics SHALL remain unchanged.

#### Scenario: G01 Repair a fully unified product with a sole receipt
- **GIVEN** every absorbed source has been fully converted and an otherwise eligible zero-valued POS issue is supported by exactly one earlier real supplier receipt
- **WHEN** the manager previews and applies ordinary stock repair
- **THEN** consolidation alone does not exclude the issue and its repaired value uses that receipt
- **AND** the selected related POS costs are updated atomically with existing audit evidence

#### Scenario: G02 Explain incomplete consolidation
- **GIVEN** only current stock was transferred, an absorbed source lacks full-history evidence, or the selected card is itself an absorbed source
- **WHEN** ordinary stock repair is previewed
- **THEN** the issue remains excluded with an actionable explanation directing the user to the canonical card and full-history conversion

#### Scenario: G03 Ignore retired transfer pairs
- **GIVEN** a proven conversion retired old consolidation transfers and otherwise eligible history contains one earlier real receipt
- **WHEN** ordinary repair evaluates the real outgoing issue
- **THEN** cancelled transfer pairs do not cause consolidation exclusion or contribute a second receipt or additional value

#### Scenario: G04 Preserve the single-receipt boundary
- **GIVEN** fully consolidated history contains multiple real receipts before a zero-valued issue
- **WHEN** ordinary repair is previewed
- **THEN** the issue remains excluded because multiple receipts exceed that mode's scope
- **AND** the explanation identifies consolidated-history recomputation as the available review path without changing the selection or any cost

#### Scenario: G05 Reject a newly absorbed source after preview
- **GIVEN** an eligible fully consolidated product has a reviewed repair plan
- **WHEN** a further source is merged before application
- **THEN** the entire old plan is rejected as stale without changing stock or POS costs

#### Scenario: G06 Reject changed absorbed-source stock after preview
- **GIVEN** a reviewed repair relied on the absence of residual source history
- **WHEN** a non-cancelled movement or nonzero stock quantity appears on an archived source before or concurrently with application
- **THEN** the old plan cannot apply using the former proof, and no partial repair is committed

#### Scenario: G07 Preserve ordinary and mixed selections
- **WHEN** a manager previews and applies ordinary or mixed-product selection containing eligible non-consolidated products, eligible fully consolidated products and ineligible products
- **THEN** each issue follows its applicable existing receipt and financial checks and only reviewed eligible results are applied
- **AND** no additional orders, products or nonzero stock values are silently added to the repair

#### Scenario: G08 Operate without consolidation integration
- **WHEN** the stock-repair module is used without the consolidation subsystem or without a callable full-history proof
- **THEN** ordinary non-consolidated products retain their existing behavior and available consolidation markers without proof retain exclusion
- **AND** no new dependency or missing-method failure prevents ordinary recomputation
