## MODIFIED Requirements

### Requirement: Manual valuation of fully consolidated history

An authorized user SHALL be able to open the existing recomputation tool from an applied full-history consolidation. Preview SHALL include the canonical products' real affected outgoing movements from the earliest affected issue through a fixed preview cutoff, including nonzero stored values and supported related POS costs outside the initial selection. It SHALL use standard historical FIFO over original receipts and SHALL exclude retired consolidation transfer pairs. Applying the reviewed plan MUST update stock values before POS costs atomically, preserving before/after evidence, quantities, revenue, payments, debts and posted accounting entries. Consolidation SHALL NOT invoke this operation automatically or add pending-recomputation flags. Existing permissions, period checks, unsupported-source rejection and stale-preview protection SHALL apply. Ordinary POS-only recomputation SHALL retain its existing semantics. Zero-stock-value repair SHALL retain its existing scope, permissions and receipt/financial restrictions while admitting proven fully consolidated canonical products under the stock-repair requirements.

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
- **THEN** their existing scope, permissions and valuation restrictions remain unchanged except that proven fully consolidated canonical products are eligible for the ordinary stock-repair checks

## ADDED Requirements

### Requirement: Explicit handoff from stock repair to consolidated-history review

When historical recomputation is installed, a skipped stock-repair detail for a proven fully consolidated canonical product SHALL offer authorized users an explicit action to open a new consolidated-history recomputation for that product and the original operation company. It MUST NOT change the original selection, switch its mode, run a preview or apply costs automatically. Before application, the destination SHALL disclose that its scope starts at the earliest affected issue, includes nonzero outgoing values and supported related POS costs outside the original selection, and ends at its fixed preview cutoff. Opening the action SHALL NOT certify that the destination history is supported: existing historical validation SHALL remain authoritative. Incomplete consolidation SHALL instead explain the required full-history conversion. Hidden or unauthorized consolidation evidence MUST NOT be exposed by the action.

#### Scenario: H01 Open an explicit broader review
- **GIVEN** a fully consolidated product was skipped because multiple earlier receipts prevent ordinary zero-value repair
- **WHEN** an authorized manager uses the action on its stock detail
- **THEN** a new unapplied consolidated-history operation opens for that product in the same company
- **AND** its broader scope is disclosed and the original operation, selections and business values remain unchanged

#### Scenario: H02 Enforce dedicated historical permission
- **GIVEN** a user may perform ordinary stock repair but lacks historical recomputation permission or access to its consolidation evidence
- **WHEN** the user inspects the skipped detail or calls the handoff action directly
- **THEN** no usable handoff is offered and a direct unauthorized request is rejected without exposing protected evidence
- **AND** ordinary permitted stock repair remains available

#### Scenario: H03 Preserve the source company
- **WHEN** the handoff is requested from a stock detail belonging to an operation in a different company from the current default company
- **THEN** it uses only evidence from the original operation company if that company is authorized, otherwise it rejects the request

#### Scenario: H04 Close or repeat the handoff without applying
- **WHEN** a user opens, closes or repeats the handoff without applying a reviewed destination plan
- **THEN** no stock value or POS cost changes and the original operation remains unchanged
- **AND** any saved destination draft requires its own preview and application

#### Scenario: H05 Revalidate completeness before opening
- **GIVEN** consolidation completeness changed since the skipped detail was prepared
- **WHEN** the user requests the handoff
- **THEN** current completeness is checked and an incomplete consolidation is rejected before opening a destination
- **AND** the reason identifies the required full-history conversion
