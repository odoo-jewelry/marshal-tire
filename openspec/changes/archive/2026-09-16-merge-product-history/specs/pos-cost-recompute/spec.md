## MODIFIED Requirements

### Requirement: Explicit bounded selection

The system SHALL provide a cost-recomputation action from the administrative POS order list and an operation-history entry. An operation MUST belong to one authorized company. In ordinary modes, users SHALL select explicit orders or a bounded order-date interval, optionally narrowed by POS configurations and products. With historical stock write-off installed, the explicit historical mode SHALL instead use selected completed historical documents to determine affected products and the earliest inclusive date through the preview cutoff; additional order, POS and product filters SHALL NOT narrow that scope. The explicit consolidated-history selection SHALL instead use applied full-history consolidations to determine the canonical products and earliest affected issue through the preview cutoff. Historical-document selection SHALL include any earlier issue boundary required by full consolidation of its products. Both history selections SHALL use all matching costs and SHALL NOT be narrowed by ordinary filters. The default ordinary mode SHALL select only lines with zero saved cost; an explicit all-lines mode SHALL also consider incorrect nonzero costs. The system MUST NOT impose a fixed maximum number of selected lines. Each operation SHALL include every matching line, SHALL freeze its line selection at preview, and MUST NOT silently truncate or expand that selection.

#### Scenario: S01 Select historical orders by filters
- **WHEN** a manager previews an operation for a company, date interval, POS configuration and product
- **THEN** only lines matching the intersection of those criteria are selected
- **AND** displayed date boundaries use the user's timezone with an inclusive start and exclusive end

#### Scenario: S02 Recompute a nonzero saved cost
- **GIVEN** a selected line has an incorrect nonzero saved cost
- **WHEN** the manager selects all-lines mode and previews it
- **THEN** the line is evaluated for recomputation
- **AND** the default zero-only mode would exclude it

#### Scenario: S03 Respect explicit order selection
- **WHEN** the manager starts from explicitly selected orders and applies additional product filters
- **THEN** the operation contains only matching lines of those orders
- **AND** it never expands to other orders matching the same dates or products

#### Scenario: S04 Reject a missing or invalid selection scope
- **WHEN** an operation lacks the required source selection for its mode or has invalid date boundaries
- **THEN** preview is rejected with an actionable explanation
- **AND** no order cost is changed and no partial selection is presented as complete

#### Scenario: S40 Process a selection exceeding the former line limit
- **GIVEN** more than 1000 eligible lines match the explicit order selection or bounded date interval
- **WHEN** the manager previews and applies the reviewed operation
- **THEN** every matching line is included and processed under the ordinary eligibility rules
- **AND** the operation neither rejects nor truncates the selection because of its line count

### Requirement: Reviewable cost proposal

Preview SHALL leave POS business records unchanged and show each selected line's order, product, signed quantity, currency, previous cost, proposed cost when available, margin difference, cost source and result status. Statuses SHALL distinguish a proposed change, unchanged values, a required acknowledgement and a skipped line with a reason. Totals SHALL be grouped by currency and SHALL distinguish cost changes from previously incomplete calculation markers. An empty or entirely skipped ordinary POS selection SHALL NOT offer application. Historical and consolidated-history modes MAY apply a reviewed nonempty stock plan even when no POS lines are affected; unsupported related POS sources SHALL reject the whole history plan rather than be silently skipped. A zero proposed unit cost SHALL require explicit acknowledgement before that line may be applied.

#### Scenario: S05 Preview before applying
- **WHEN** a manager previews an eligible operation
- **THEN** previous and proposed costs, margin differences and source explanations are displayed
- **AND** no saved POS cost or calculation-completion marker changes

#### Scenario: S06 Acknowledge a zero source
- **GIVEN** a selected line has a supported source with zero unit cost
- **WHEN** the manager attempts to apply without acknowledging the zero result
- **THEN** application is rejected
- **AND** the interface explains that recomputation cannot repair the underlying zero source

#### Scenario: S07 Report an empty or skipped selection
- **WHEN** ordinary POS preview finds no selected lines or every selected line is ineligible
- **THEN** the interface displays the empty result or individual skip reasons
- **AND** application is unavailable

## ADDED Requirements

### Requirement: Manual valuation of fully consolidated history

An authorized user SHALL be able to open the existing recomputation tool from an applied full-history consolidation. Preview SHALL include the canonical products' real affected outgoing movements from the earliest affected issue through a fixed preview cutoff, including nonzero stored values and supported related POS costs outside the initial selection. It SHALL use standard historical FIFO over original receipts and SHALL exclude retired consolidation transfer pairs. Applying the reviewed plan MUST update stock values before POS costs atomically, preserving before/after evidence, quantities, revenue, payments, debts and posted accounting entries. Consolidation SHALL NOT invoke this operation automatically or add pending-recomputation flags. Existing permissions, period checks, unsupported-source rejection and stale-preview protection SHALL apply. Ordinary cost recomputation and zero-stock-value repair SHALL retain their existing semantics.

#### Scenario: C01 Start from a completed merge
- **WHEN** an authorized user opens manual recomputation from an applied full-history consolidation
- **THEN** the existing tool selects its canonical products and earliest affected issue through the preview cutoff
- **AND** no cost changes until the reviewed plan is applied

#### Scenario: C02 Recompute nonzero merged costs
- **GIVEN** the combined original receipt sequence changes a subsequent issue's stored nonzero cost
- **WHEN** the user applies the reviewed consolidated-history plan
- **THEN** that issue and every other affected supported issue are revalued using standard historical FIFO before their related POS costs
- **AND** real receipt values, quantities and commercial amounts remain unchanged

#### Scenario: C03 Exclude retired transfer receipts
- **GIVEN** an old consolidation pair has been retired by full-history conversion
- **WHEN** a consolidated-history cost plan is calculated
- **THEN** only the real original receipts contribute to the FIFO sequence and the retired pair is absent from active valuation

#### Scenario: C04 Reject stale plans
- **GIVEN** sources change after preview
- **WHEN** application is requested
- **THEN** the plan is refused with an actionable reason and no partial stock or POS cost changes

#### Scenario: C07 Reject unsupported valuation
- **GIVEN** required valuation would touch an unsupported or protected history
- **WHEN** consolidated-history recomputation is previewed
- **THEN** the entire plan is rejected with the unsupported records identified

#### Scenario: C05 Apply a stock-only plan
- **GIVEN** a valid consolidated-history plan has affected stock issues and no related POS lines
- **WHEN** the user applies it
- **THEN** reviewed stock values are updated with audit evidence without requiring a POS sale

#### Scenario: C06 Preserve ordinary cost tools
- **WHEN** users run ordinary POS cost recomputation or zero-stock-value repair without consolidated-history selection
- **THEN** their existing scope, permissions and valuation restrictions remain unchanged
