## MODIFIED Requirements

### Requirement: Supported historical quantities and valuation

Application SHALL validate recorded quantities at the requested business timestamp, the subsequent stock history and current availability. It MUST NOT invent missing opening stock, consume another operation's reserved stock, or silently produce negative quantities through insertion into history. Valuation SHALL follow the standard costing policy for the supported historical case, including FIFO where applicable. Later receipts and today's fallback cost MUST NOT silently substitute for evidence needed at the historical timestamp. The operation SHALL validate that the affected history supports subsequent manual valuation recomputation without rewriting pre-existing posted financial documents. Stock completion SHALL NOT claim that later stored costs have already been recomputed. A canonical product with verified full history consolidation SHALL be evaluated from its unified original movements; absorbed-card links alone MUST NOT cause rejection. Unconverted stock-only consolidations SHALL remain ineligible and identify the required conversion. An unsupported or ambiguous history SHALL be rejected with an actionable reason; using today's date instead SHALL NOT count as successful historical application.

#### Scenario: S12 Reject insufficient historical stock
- **GIVEN** the selected date precedes recorded availability of a required product
- **WHEN** the user applies the stock write-off
- **THEN** application is rejected with the affected product and shortage
- **AND** no opening balance or earlier receipt is fabricated

#### Scenario: S13 Validate the subsequent history
- **GIVEN** stock was sufficient at the selected timestamp but insertion would cause a later shortage, consume current reservations, or prevent the supported subsequent manual valuation recomputation
- **WHEN** the user applies the stock write-off
- **THEN** application is rejected without changing later movements or their posted financial effects

#### Scenario: S14 Reject an unproven valuation path
- **WHEN** the product's historical valuation or downstream impact cannot be determined through the supported standard costing path
- **THEN** the system explains the unsupported condition and leaves the document unposted
- **AND** it does not use zero sale prices, later receipt costs, or current execution time as an unannounced substitute

#### Scenario: H01 Consume a fully unified receipt history
- **GIVEN** full consolidation has combined original August 28 receipts of 20 and 100 units and all other historical checks pass
- **WHEN** the user applies a 31-unit write-off on August 31
- **THEN** the write-off uses the canonical product's combined availability without a generic consolidated-product rejection
- **AND** stock consumption creates no revenue, payment, debt or new session

#### Scenario: H02 Explain an unconverted consolidation
- **GIVEN** the target still has an old stock-only consolidation
- **WHEN** historical consumption is requested
- **THEN** the operation identifies the source group requiring full history conversion and remains unposted

#### Scenario: H03 Retain quantity safeguards after consolidation
- **GIVEN** a fully consolidated product has insufficient historical stock or would develop a later shortage
- **WHEN** historical consumption is requested
- **THEN** it is rejected under the same quantity rules as an ordinary product


### Requirement: Manual recomputation from the earliest historical consumption

After one or more historical consumptions, an authorized user SHALL be able to
invoke the existing cost-recomputation tool in a dedicated historical mode.
Selected completed historical documents SHALL determine the earliest inclusive
business timestamp and affected products within one company. For fully consolidated products, the system SHALL expand the inclusive start when necessary to cover the earliest affected outgoing movement identified by their applied consolidation history, including earlier affected issues before the selected consumption. Preview SHALL include
all subsequent affected outgoing movements through the preview cutoff, including
nonzero values and operations outside the initially selected receipts, together
with their supported completed POS costs. Applying a reviewed plan SHALL update
stock values first and POS costs second, atomically, using standard historical FIFO
calculations and preserving before/after audit evidence. Revenue, payments, debts,
quantities and posted accounting entries MUST remain unchanged by recomputation.
Ordinary cost-recomputation and zero-stock-value-repair modes SHALL remain unchanged.
No automatic invocation or separate pending-recomputation marker SHALL be added.

#### Scenario: S25 Recompute from the earliest of multiple transfers
- **GIVEN** several completed historical consumptions affect a product at different dates
- **WHEN** the user selects them and manually previews historical recomputation
- **THEN** all affected subsequent stock issues are evaluated from the earliest selected date
- **AND** existing nonzero values and related eligible POS costs are included, not only the selected source receipts

#### Scenario: S26 Apply stock costs before POS costs
- **GIVEN** an earlier inserted consumption changes a later issue's FIFO cost from 200 to 300
- **WHEN** the user manually applies the reviewed historical recomputation
- **THEN** that issue's stored value becomes 300 before its linked eligible POS costs are recomputed
- **AND** the original and new values remain auditable without changing revenue, payments or quantities

#### Scenario: S27 Preserve manual control without pending markers
- **WHEN** a historical consumption completes
- **THEN** the user may separately start cost recomputation
- **AND** no automatic downstream recomputation or additional pending marker is created

#### Scenario: S28 Reject stale or unsupported manual recomputation
- **WHEN** relevant history changes after preview or cannot be recomputed under the supported costing and financial constraints
- **THEN** applying the proposed plan is rejected without partial cost changes
- **AND** the user receives a reason and must review current data

#### Scenario: H04 Include earlier costs affected by a merge
- **GIVEN** full consolidation affects an issue dated before the selected historical consumption
- **WHEN** the user previews manual historical recomputation
- **THEN** the displayed start includes that earlier issue and all subsequent affected issues through the cutoff
- **AND** both merge and consumption reasons for the expanded range are visible
