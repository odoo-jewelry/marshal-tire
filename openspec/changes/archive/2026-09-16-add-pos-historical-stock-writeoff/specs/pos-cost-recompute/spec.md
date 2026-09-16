## MODIFIED Requirements

### Requirement: Explicit bounded selection

The system SHALL provide a cost-recomputation action from the administrative POS order list and an operation-history entry. An operation MUST belong to one authorized company. In ordinary modes, users SHALL select explicit orders or a bounded order-date interval, optionally narrowed by POS configurations and products. With historical stock write-off installed, the explicit historical mode SHALL instead use selected completed historical documents to determine affected products and the earliest inclusive date through the preview cutoff; additional order, POS and product filters SHALL NOT narrow that scope. The default mode SHALL select only lines with zero saved cost; an explicit all-lines mode SHALL also consider incorrect nonzero costs. The system MUST NOT impose a fixed maximum number of selected lines. Each operation SHALL include every matching line, SHALL freeze its line selection at preview, and MUST NOT silently truncate or expand that selection.

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
- **WHEN** an operation lacks both explicit orders and a bounded date interval or has invalid date boundaries
- **THEN** preview is rejected with an actionable explanation
- **AND** no order cost is changed and no partial selection is presented as complete

#### Scenario: S40 Process a selection exceeding the former line limit
- **GIVEN** more than 1000 eligible lines match the explicit order selection or bounded date interval
- **WHEN** the manager previews and applies the reviewed operation
- **THEN** every matching line is included and processed under the ordinary eligibility rules
- **AND** the operation neither rejects nor truncates the selection because of its line count

### Requirement: Reviewable cost proposal

Preview SHALL leave POS business records unchanged and show each selected line's order, product, signed quantity, currency, previous cost, proposed cost when available, margin difference, cost source and result status. Statuses SHALL distinguish a proposed change, unchanged values, a required acknowledgement and a skipped line with a reason. Totals SHALL be grouped by currency and SHALL distinguish cost changes from previously incomplete calculation markers. An empty or entirely skipped ordinary POS selection SHALL NOT offer application. Historical mode MAY apply a reviewed nonempty stock plan even when no POS lines are affected; unsupported related POS sources SHALL reject the historical plan rather than be silently skipped. A zero proposed unit cost SHALL require explicit acknowledgement before that line may be applied.

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
- **WHEN** preview finds no selected lines or every selected line is ineligible
- **THEN** the interface displays the empty result or individual skip reasons
- **AND** application is unavailable

### Requirement: Supported standard cost semantics

For eligible lines outside stock-valued FIFO and average-cost products, recomputation SHALL use the current product cost of the order company. For eligible stock-valued FIFO and average-cost lines, it SHALL use existing completed stock valuation sources and the standard weighted unit-cost calculation. Cost amounts SHALL preserve the signed POS quantity and use standard conversion from cost currency to order currency at the order date without intermediate rounding. Ordinary recomputation MUST NOT substitute current product cost for unavailable or ambiguous stock valuation and MUST NOT claim to restore historical acquisition costs. Explicit historical mode SHALL use the supported standard historical FIFO calculation for reviewed subsequent issues, without fabricating receipt costs or missing opening quantities. Product cost methods and units are interpreted as currently configured; historical configuration changes are outside automatic reconstruction.

#### Scenario: S08 Recompute from current standard cost
- **GIVEN** a line sold two units, its saved cost is zero, its order currency equals cost currency, and its product now has standard unit cost 40
- **WHEN** the reviewed operation is applied
- **THEN** the saved line cost becomes 80 and its calculation is marked complete

#### Scenario: S09 Preserve service cost semantics
- **GIVEN** an eligible service line has no stock movement and a current company unit cost of 15
- **WHEN** two sold units are recomputed in the same currency
- **THEN** the saved line cost becomes 30 without requiring a stock movement

#### Scenario: S10 Use existing FIFO or average valuation
- **GIVEN** eligible stock movements value two units at a total of 60 while the product card shows a unit cost of 50
- **WHEN** a corresponding two-unit FIFO or average-cost sale is recomputed
- **THEN** its cost becomes 60 rather than 100

#### Scenario: S11 Convert cost in the order context
- **GIVEN** cost and order currencies differ and the applicable rate differs between the order date and today
- **WHEN** a line is recomputed
- **THEN** its company-specific source is converted at the order-date rate without intermediate rounding
- **AND** amounts in different currencies are not added into an unlabeled total

### Requirement: Atomic reviewed application

Application SHALL require a nonempty reason, an explicit confirmation and a current server-generated preview. It MUST revalidate authorization, selected records, source identity and relevant values before any cost update. An external change to a source, cost, quantity, lifecycle condition or conversion input SHALL invalidate the whole preview. In explicit stock-repair or historical mode, only the fixed stock-value changes included in the reviewed plan MAY be applied before POS recomputation; they are authorized parts of that same transaction, not external stale-preview changes. The operation SHALL apply only its reviewed eligible lines in one transaction; an unexpected failure MUST roll back all cost, completion-marker and success-history changes. No intermediate commits or silent runtime skips are permitted. Parallel or repeated requests for the same applied operation SHALL return its existing result, and overlapping operations SHALL not overwrite changes using stale previews.

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

After application, standard POS line and order margins and the POS sales-analysis report SHALL reflect updated saved costs using their existing formulas. Quantities, sales prices, discounts, taxes, totals, payments, invoices, accounting entries, stock movement identities, dates and dimensions, receipt values and product costs MUST remain unchanged by the operation. Ordinary recomputation MUST also leave all stock valuation amounts unchanged. Explicit stock-repair mode MAY change only the reviewed eligible zero-valued outgoing movements under the stock-repair requirements, followed by recomputation of their fully selected POS lines. Explicit historical mode MAY also update reviewed nonzero outgoing values from the earliest selected historical consumption, followed by all supported related POS costs. Both modes MUST NOT create stock movements or financial postings. Installation or upgrade SHALL NOT trigger historical recomputation. Ordinary POS sale, refund, invoicing and session-closing workflows SHALL retain their existing behavior when this feature is not invoked.

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
