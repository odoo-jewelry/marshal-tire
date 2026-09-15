## Purpose

Allow authorized POS managers to recompute historical POS line costs through a reviewed, bounded, auditable operation using supported standard Odoo cost sources.

## ADDED Requirements

### Requirement: Explicit bounded selection

The system SHALL provide a cost-recomputation action from the administrative POS order list and an operation-history entry. An operation MUST belong to one authorized company. Users SHALL select explicit orders or a bounded order-date interval, optionally narrowed by POS configurations and products. The default mode SHALL select only lines with zero saved cost; an explicit all-lines mode SHALL also consider incorrect nonzero costs. Each operation SHALL include at most 1000 selected lines before eligibility exclusions, SHALL freeze its line selection at preview, and MUST NOT silently truncate or expand that selection.

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

#### Scenario: S04 Reject an oversized or unbounded selection
- **WHEN** an operation lacks both explicit orders and a bounded date interval, has invalid date boundaries, or selects more than 1000 lines
- **THEN** preview is rejected with an actionable explanation
- **AND** no order cost is changed and no partial selection is presented as complete

### Requirement: Reviewable cost proposal

Preview SHALL leave POS business records unchanged and show each selected line's order, product, signed quantity, currency, previous cost, proposed cost when available, margin difference, cost source and result status. Statuses SHALL distinguish a proposed change, unchanged values, a required acknowledgement and a skipped line with a reason. Totals SHALL be grouped by currency and SHALL distinguish cost changes from previously incomplete calculation markers. An empty or entirely skipped selection SHALL NOT offer application. A zero proposed unit cost SHALL require explicit acknowledgement before that line may be applied.

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

For eligible lines outside stock-valued FIFO and average-cost products, recomputation SHALL use the current product cost of the order company. For eligible stock-valued FIFO and average-cost lines, it SHALL use existing completed stock valuation sources and the standard weighted unit-cost calculation. Cost amounts SHALL preserve the signed POS quantity and use standard conversion from cost currency to order currency at the order date without intermediate rounding. The operation MUST NOT substitute current product cost for unavailable or ambiguous stock valuation and MUST NOT claim to restore historical acquisition costs. Product cost methods and units are interpreted as currently configured; historical configuration changes are outside automatic reconstruction.

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

### Requirement: Stock-source resolution and lifecycle eligibility

Only paid or posted orders in closed POS sessions SHALL be eligible. Stock-valued FIFO and average-cost lines MUST have a supported completed valuation source with positive valued quantity and no relevant unfinished movement. Direct order movements SHALL take precedence over session movements. If there are no direct movements and normal stock processing occurred at session closure, the operation SHALL consider the complete relevant session-level source for the product, including movements attributable to unselected orders. It SHALL label the result as a session-level weighted cost, not an exact historical line allocation. A source containing opposite sale and return directions, inconsistent direction, unavailable valuation, or an unprovable association SHALL cause the affected line to be skipped. The system SHALL NOT create or finish stock movements to make a line eligible.

#### Scenario: S12 Resolve aggregate session movements
- **GIVEN** a closed session has only outgoing completed movements for a selected product, totalling four valued units and value 100, with no direct picking on the selected order
- **WHEN** a one-unit sale from that session is recomputed
- **THEN** its cost becomes 25 in the same currency
- **AND** preview identifies the session-level weighted source, including quantities from unselected orders

#### Scenario: S13 Prefer direct order movements
- **GIVEN** an order has its own completed movements and its session also contains other movements of that product
- **WHEN** its cost is recomputed
- **THEN** only its supported direct source is used without adding the session source

#### Scenario: S14 Skip mixed sale and return stock sources
- **GIVEN** the candidate source for a product includes both outgoing sales and incoming returns
- **WHEN** a selected line of that product is previewed
- **THEN** the line is skipped with an ambiguous-source explanation
- **AND** restricting selection to sales alone does not hide the return movements from that check

#### Scenario: S15 Skip an open session
- **WHEN** a paid order in an open or closing session is selected
- **THEN** its lines are skipped with a session-not-closed explanation
- **AND** the operation neither closes the session nor marks deferred costs complete

#### Scenario: S16 Skip incomplete or missing valuation
- **WHEN** a stock-valued line has relevant unfinished delivery movements, no provable completed source, or zero valued quantity
- **THEN** the line retains its saved cost and completion marker
- **AND** the result explains the missing or incomplete source

#### Scenario: S17 Exclude draft and cancelled orders
- **WHEN** a draft or cancelled order is selected
- **THEN** its lines are reported as ineligible without changing the order

### Requirement: Explicit return limitations

Supported returns SHALL retain standard signed-cost semantics. A standard-cost return SHALL use current company product cost; a stock-valued return SHALL use its supported existing return valuation source. Recalculation SHALL NOT invent a link to an original sale movement or guarantee that sale and return costs cancel when their sources differ. Linked sale or return lines outside the frozen selection SHALL remain unchanged and SHALL be identified as related records outside the operation. The first version SHALL skip the special deferred-delivery branch that would substitute a zero movement cost with product cost or original POS line cost, explaining that it requires separate review.

#### Scenario: S18 Recompute a partial standard-cost return
- **GIVEN** a selected return contains quantity minus one for a product with current standard unit cost 40 in the same currency
- **WHEN** the return is recomputed
- **THEN** its cost becomes minus 40 regardless of the originally saved sale cost
- **AND** preview explains the current-cost basis

#### Scenario: S19 Reuse a return movement valuation
- **GIVEN** a completed return movement values one returned unit at 30 using its existing original-movement association
- **WHEN** the corresponding eligible FIFO or average-cost return is recomputed in the same currency
- **THEN** its saved cost becomes minus 30 without modifying either movement

#### Scenario: S20 Keep unselected linked orders unchanged
- **GIVEN** a selected sale has a linked return outside the frozen selection
- **WHEN** the operation is previewed and applied
- **THEN** the related return is identified as outside the operation and remains unchanged
- **AND** no claim is made that their resulting margins necessarily cancel

#### Scenario: S21 Skip deferred-delivery zero-cost substitution
- **GIVEN** a deferred-delivery sale or return would require substitution of a zero movement cost
- **WHEN** it is previewed
- **THEN** the affected line is skipped with a specific unsupported-fallback explanation

### Requirement: Observable handling of unsupported structures

The first version SHALL skip zero-quantity lines, POS combo structures, manufacturing kits, and known project correction chains rather than inventing their cost allocation. This exclusion SHALL also cover session-level stock sources affected by project corrections. Archived products SHALL remain selectable through historical orders and SHALL be handled normally when all other conditions are supported. Other independently eligible selected lines MAY be applied, provided every skip is visible before confirmation and retained in the result.

#### Scenario: S22 Report unsupported structures
- **WHEN** selected lines include zero quantities, combo structures or manufacturing kits
- **THEN** those lines are skipped with specific reasons
- **AND** ordinary supported lines remain available for review

#### Scenario: S23 Isolate project correction chains
- **GIVEN** project corrections affect a selected order or its candidate shared stock source
- **WHEN** the operation is previewed
- **THEN** the affected lines are skipped without changing correction history or allocations

#### Scenario: S24 Process an archived product
- **GIVEN** an eligible historical line references an archived product
- **WHEN** it is selected through its order
- **THEN** it can be recomputed using the same eligibility and cost rules as an active product

### Requirement: Atomic reviewed application

Application SHALL require a nonempty reason, an explicit confirmation and a current server-generated preview. It MUST revalidate authorization, selected records, source identity and relevant values before any cost update. A changed source, cost, quantity, lifecycle condition or conversion input SHALL invalidate the whole preview. The operation SHALL apply only its reviewed eligible lines in one transaction; an unexpected failure MUST roll back all cost, completion-marker and success-history changes. No intermediate commits or silent runtime skips are permitted. Parallel or repeated requests for the same applied operation SHALL return its existing result, and overlapping operations SHALL not overwrite changes using stale previews.

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

### Requirement: Authorization and protected history

Creating previews and applying operations SHALL require POS manager permission and normal access to all affected records and cost sources. Every operation and detail SHALL be restricted to its authorized company. Application SHALL retain the acting user, application time, reason, reviewed selection, sources, before and after costs and markers, and skipped reasons. Applied operations and their details SHALL be immutable through ordinary editing, deletion, copying, import and direct requests; duplicated drafts SHALL contain only fresh editable selection criteria. Direct calls MUST enforce the same rules as the interface and MUST NOT trust client-supplied computed results.

#### Scenario: S32 Reject an unauthorized direct request
- **WHEN** a non-manager or a manager lacking required record access directly requests preview or application
- **THEN** the request fails without exposing unavailable source costs or changing records

#### Scenario: S33 Preserve company isolation
- **WHEN** an operation mixes orders from different companies or references an unauthorized company
- **THEN** it is rejected
- **AND** an authorized single-company operation always reads that order company's product cost

#### Scenario: S34 Inspect applied history
- **WHEN** an authorized manager opens an applied operation
- **THEN** its author, time, reason, selected lines, sources, previous and resulting values and skip reasons remain available

#### Scenario: S35 Protect results from editing and forgery
- **WHEN** ordinary editing, import, copying or a direct request attempts to forge preview amounts, alter applied history or reapply an applied copy
- **THEN** it is rejected or creates only a fresh draft containing selection criteria
- **AND** no forged cost update is applied

### Requirement: POS reporting and operational continuity

After application, standard POS line and order margins and the POS sales-analysis report SHALL reflect updated saved costs using their existing formulas. Quantities, sales prices, discounts, taxes, totals, payments, invoices, accounting entries, stock movements, valuation amounts and product costs MUST remain unchanged by the operation. Installation or upgrade SHALL NOT trigger historical recomputation. Ordinary POS sale, refund, invoicing and session-closing workflows SHALL retain their existing behavior when this feature is not invoked.

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
