## MODIFIED Requirements

### Requirement: Traceable revision history

The source order SHALL expose the latest applied effective sale as its default working view. The unchanged original document and all correction revisions SHALL be available through change history, with original values clearly distinguished from current values. Every applied correction SHALL retain its reason, author, time, previous and resulting values, and links to generated documents. Repeated corrections SHALL use the latest effective sale. Saving or cancelling a draft SHALL NOT change that effective sale. Applied history and generated documents SHALL NOT be silently edited, deleted or duplicated; an applied correction SHALL be undone only by a new eligible correction. Correcting an error from an earlier applied revision SHALL start from the latest effective sale and SHALL NOT rewrite that earlier revision or automatically replay intervening revisions.

#### Scenario: S30 Inspect correction history
- **WHEN** a user opens the history of a corrected source order
- **THEN** the original receipt and every correction revision are accessible, with the correction state, reason, author, application time and links to operational documents
- **AND** an applied revision offers a readable comparison of its previous and resulting values while drafts and cancelled preparations remain distinguishable from applied changes

#### Scenario: S31 Correct the latest result
- **GIVEN** a sale originally containing A has already been corrected to B
- **WHEN** another correction replaces B with C
- **THEN** only the effective B is offset and the resulting effective sale contains C

#### Scenario: S32 Protect applied history
- **WHEN** editing, deletion, cancellation or duplication attempts to rewrite or reapply an applied correction or its generated records outside the correction workflow
- **THEN** the request is rejected or, for an ordinary source-order copy, correction ownership is cleared without generating correction effects

#### Scenario: S40 Undo through another correction
- **GIVEN** an eligible sale of A was corrected to B
- **WHEN** the user applies a new correction restoring A and the original payment distribution
- **THEN** the effective result is restored through a new traceable revision while the previous revision and its documents remain intact

#### Scenario: S45 Prepare a third correction
- **GIVEN** an eligible sale has two applied corrections
- **WHEN** the user starts another correction from its source order
- **THEN** editable products and payment distribution are initialized from the second applied result and applying the changes records a new revision

#### Scenario: S46 Correct an earlier mistake after later changes
- **GIVEN** the second applied correction set an incorrect quantity and the third applied correction changed the payment distribution
- **WHEN** the user prepares a fourth correction from the current sale, changes the quantity and adjusts payments as required by the resulting total
- **THEN** the fourth correction changes the latest effective sale while preserving unchanged current values and all three prior revisions

#### Scenario: S47 Continue an unapplied correction
- **GIVEN** the source order has an existing draft correction
- **WHEN** the user starts correction again
- **THEN** that draft is reopened without discarding its edits or creating a second preparation, and existing stale-data validation still applies on application

## ADDED Requirements

### Requirement: Current receipt as the primary administrative view

The administrative source-order form SHALL present products and recorded payments on separate ordinary Products and Payments tabs. For a source with applied corrections these tabs SHALL show the latest effective products, payment distribution and sale total, with effective data read-only outside correction preparation. Original values SHALL be accessed through history rather than competing Original Products, Original Payments or Current Sale tabs. For an order without applied corrections, standard products, payments, totals and editing behavior SHALL remain available. Empty effective products or payments SHALL NOT cause fallback to original values. The current payment distribution SHALL represent recorded sale allocation, not a new external transaction or subsequent debt settlement.

#### Scenario: S48 Open the current corrected receipt
- **GIVEN** a receipt originally totalled 100 and its latest applied correction changed it to 120
- **WHEN** the user opens the source order
- **THEN** the default Products tab shows the effective items and total 120, and the Payments tab shows the effective allocation rather than only the correction difference
- **AND** the original total 100 is available through history without a competing original tab in the working receipt

#### Scenario: S49 Find current payments independently of products
- **GIVEN** a receipt originally recorded cash 100 and an applied correction changed registration to bank 100
- **WHEN** the user opens its Payments tab
- **THEN** the effective distribution is bank 100 with no nonzero cash allocation, and the sale total is 100
- **AND** the original cash registration and its offset remain accessible through history

#### Scenario: S50 Keep preparation separate from the current receipt
- **GIVEN** a source order has an applied correction and a later draft with different products or payments
- **WHEN** the user saves or cancels that draft and opens the source order
- **THEN** the working tabs still show the last applied result, and history identifies the preparation by its actual state

#### Scenario: S51 Preserve orders without applied corrections
- **WHEN** a user opens an ordinary order, including a draft, a cancelled order, an ordinary return, or an order with only draft or cancelled correction preparations
- **THEN** standard products, payments, totals, signs and editing permissions are preserved without misleading original/current tab duplication
- **AND** correction eligibility remains unchanged

#### Scenario: S62 Display an empty effective sale
- **GIVEN** an applied correction removed all sale items and effective payment allocation
- **WHEN** the user opens the source order
- **THEN** the working Products and Payments tabs show an empty effective sale and zero total without restoring original items or amounts

### Requirement: Navigation returns to the effective receipt

Successful correction application SHALL open the source order with its latest effective sale. Retrying an applied correction SHALL open the same source order without generating additional effects; if newer revisions exist, the working form SHALL show the newest applied state. Generated difference documents SHALL remain separately accessible from history and correction details, SHALL be visibly identified as correction operations, and SHALL offer navigation to the effective source receipt. Opening a difference document SHALL continue to show that document's own operational values.

#### Scenario: S52 Apply and return to the receipt
- **WHEN** a user successfully applies a correction
- **THEN** the returned form is the source receipt with updated effective products, payments and total rather than the generated difference document

#### Scenario: S53 Retry an older applied correction
- **GIVEN** an applied correction has already been followed by a newer applied correction
- **WHEN** application of the older correction is retried
- **THEN** no documents or movements are created and the source receipt opens with the newest applied result

#### Scenario: S54 Inspect a difference and return
- **WHEN** a user opens a generated document from correction history
- **THEN** the form clearly identifies it as a correction difference, shows its own items, payments and total, and offers return to the effective source receipt

### Requirement: Readable original and revision details

Change history SHALL provide read-only access to the original receipt and human-readable Before and After views of each applied revision's recorded products, quantities, unit prices, discounts, taxes, tracked identifiers, product attributes where recorded, and payment distribution. Reading these values SHALL NOT require interpreting technical serialized data. Earlier revision details SHALL remain tied to the recorded values for that revision after later corrections. Missing historical values SHALL be identified as unavailable rather than inferred from the current sale or recalculated under current tax settings. Viewing history SHALL respect existing record access and company restrictions and SHALL NOT modify documents or grant correction permission.

#### Scenario: S55 Read the original receipt from history
- **GIVEN** a receipt has several applied corrections
- **WHEN** the user opens its original version from history
- **THEN** the original items, payment records, total, date and session are shown read-only and clearly labelled as original values

#### Scenario: S56 Compare an intermediate revision
- **GIVEN** a receipt has three applied corrections
- **WHEN** the user opens the second revision
- **THEN** readable Before and After values describe the second revision's own change, including its product and payment values, rather than substituting the third revision's result

#### Scenario: S57 Display incomplete historical details honestly
- **GIVEN** an existing revision lacks a recorded detail or references a deleted or inaccessible descriptive record
- **WHEN** an authorized user reads its comparison
- **THEN** the available recorded values remain readable and the unavailable detail is identified without inventing historical values or exposing restricted record contents

#### Scenario: S58 Restrict history navigation and display
- **WHEN** a user invokes a history, original-receipt or return-to-receipt action for records outside their access or active companies
- **THEN** protected contents are not exposed through the action or its rendered comparison, and no additional editing or correction rights are granted

### Requirement: Presentation continuity during correction interface upgrades

The interface change SHALL preserve pending stock and session-closure notices, standard correction validation and permissions, and operational accounting, payment, stock and debt behavior. Installation or upgrade SHALL NOT rewrite original orders or recorded revisions, create operational documents, or require fabricated historical snapshots. Standard order list and search selection, receipt number, customer, total and status columns, and optional debt-column behavior SHALL remain unchanged.

#### Scenario: S59 Preserve pending processing notices
- **GIVEN** a corrected sale awaits stock processing or correction-session closure
- **WHEN** the user opens the effective receipt
- **THEN** the applicable pending notice remains visible and the current presentation does not imply that deferred operations have completed

#### Scenario: S60 Upgrade existing correction history
- **WHEN** the module is upgraded on a database containing original orders, applied revisions and draft preparations
- **THEN** existing records become accessible through the updated presentation without rewriting history, changing draft contents or generating new operational effects

#### Scenario: S61 Preserve the standard orders list
- **WHEN** the user opens the standard Orders action after installation or upgrade
- **THEN** its standard list and search remain selected, receipt number, customer, total and status retain their established arrangement, and debt columns retain their optional behavior
