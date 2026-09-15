## MODIFIED Requirements

### Requirement: Atomic reviewed application

Application SHALL require a nonempty reason, an explicit confirmation and a current server-generated preview. It MUST revalidate authorization, selected records, source identity and relevant values before any cost update. An external change to a source, cost, quantity, lifecycle condition or conversion input SHALL invalidate the whole preview. In explicit stock-repair mode, only the fixed stock-value changes included in the reviewed repair plan MAY be applied before POS recomputation; they are authorized parts of that same transaction, not external stale-preview changes. The operation SHALL apply only its reviewed eligible lines in one transaction; an unexpected failure MUST roll back all cost, completion-marker and success-history changes. No intermediate commits or silent runtime skips are permitted. Parallel or repeated requests for the same applied operation SHALL return its existing result, and overlapping operations SHALL not overwrite changes using stale previews.

#### Scenario: S25 Apply a reviewed mixed selection
- **GIVEN** preview contains eligible and explicitly skipped lines and all required acknowledgements are present
- **WHEN** the manager confirms with a reason
- **THEN** only reviewed eligible lines are applied and skipped lines remain unchanged
- **AND** the result counts changed, unchanged, completion-only and skipped lines separately

#### Scenario: S26 Reject stale preview data
- **GIVEN** a relevant product cost, valuation source, order quantity, saved cost or exchange-rate input changed after preview
- **WHEN** application is requested
- **THEN** the entire operation is rejected without cost updates and requires a fresh preview

#### Scenario: S27 Roll back a runtime failure
- **WHEN** a required write or access check fails after processing has started
- **THEN** all updates of the operation are rolled back
- **AND** no successful application history is recorded

#### Scenario: S28 Retry or concurrently submit the same operation
- **WHEN** the same operation receives repeated or concurrent application requests
- **THEN** at most one request performs the updates
- **AND** another caller receives the existing result or a retryable busy response while processing is still active
- **AND** retry after success returns the same applied result without duplicate changes or history

#### Scenario: S29 Reject overlapping stale operations
- **GIVEN** two operations preview the same line and the first changes its saved cost or completion marker
- **WHEN** the second operation attempts application
- **THEN** the second is rejected as stale rather than overwriting the first result

#### Scenario: S30 Cancel before application
- **WHEN** a manager cancels a draft or previewed operation
- **THEN** no POS cost changes and the cancelled operation cannot be applied

#### Scenario: S31 Recompute again with unchanged inputs
- **GIVEN** a previous operation completed and all relevant inputs remain unchanged
- **WHEN** a new all-lines operation previews the same lines
- **THEN** their values are reported as unchanged without cumulative cost or margin drift

### Requirement: POS reporting and operational continuity

After application, standard POS line and order margins and the POS sales-analysis report SHALL reflect updated saved costs using their existing formulas. Quantities, sales prices, discounts, taxes, totals, payments, invoices, accounting entries, stock movement identities, dates and dimensions, receipt values and product costs MUST remain unchanged by the operation. Ordinary recomputation MUST also leave all stock valuation amounts unchanged. Explicit stock-repair mode MAY change only the reviewed eligible zero-valued outgoing movements under the stock-repair requirements, followed by recomputation of their fully selected POS lines. It MUST NOT create stock movements or financial postings. Installation or upgrade SHALL NOT trigger historical recomputation. Ordinary POS sale, refund, invoicing and session-closing workflows SHALL retain their existing behavior when this feature is not invoked.

#### Scenario: S36 Refresh standard POS margin reporting
- **GIVEN** a same-currency two-unit sale has untaxed revenue 120 and its reviewed cost changes from zero to 80
- **WHEN** the operation completes and the order and sales analysis are refreshed
- **THEN** their margin for that sale is 40 using the standard report formulas

#### Scenario: S37 Preserve invoiced order accounting and stock
- **GIVEN** an eligible historical order has a posted invoice and completed stock processing
- **WHEN** its POS cost is recomputed
- **THEN** invoice, accounting, payments, stock quantities, stock valuation and product costs remain unchanged
- **AND** the original sale quantities, prices, discounts, taxes and totals are preserved

#### Scenario: S38 Preserve ordinary workflows
- **WHEN** ordinary POS sales, returns, invoicing and session closures run without invoking recomputation
- **THEN** those workflows retain standard Odoo behavior

#### Scenario: S39 Install and upgrade without recomputation
- **WHEN** the module is installed or upgraded on a database containing historical POS orders
- **THEN** no historical POS cost is rewritten by installation or upgrade
