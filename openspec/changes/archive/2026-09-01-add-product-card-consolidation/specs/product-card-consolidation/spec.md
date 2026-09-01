## Purpose

This capability lets authorized users retire a duplicate product card in favor of one canonical card while preserving operational history and making future product resolution converge on the canonical product.

## ADDED Requirements

### Requirement: Controlled consolidation selection

The system SHALL allow an authorized user to start consolidation only from exactly two active single-variant product cards and SHALL require the user to choose one of them as the canonical card.

#### Scenario: Preview an eligible pair
- **GIVEN** two active single-variant product cards are selected
- **WHEN** an authorized user starts consolidation and chooses the canonical card
- **THEN** the system shows a preview identifying the canonical card, duplicate card, transferable data, preserved references, and any blockers

#### Scenario: Reject an invalid selection count
- **WHEN** a user starts consolidation with fewer or more than two product cards
- **THEN** the system refuses to open a valid consolidation preview and explains that exactly two cards are required

#### Scenario: Cancel before confirmation
- **GIVEN** a consolidation preview is open
- **WHEN** the user cancels or closes it without confirmation
- **THEN** neither product card nor any related record is changed

### Requirement: Product compatibility safeguards

The system MUST block consolidation when the selected cards are not safely compatible for logical consolidation.

#### Scenario: Reject multi-variant templates
- **GIVEN** at least one selected card belongs to a template with more than one variant
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and the variant limitation is reported

#### Scenario: Reject incompatible identity and inventory settings
- **GIVEN** the selected cards differ in company ownership, product kind, unit-of-measure category, unit of measure, or storage behavior
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and every incompatible setting is reported

#### Scenario: Reject tracked products
- **GIVEN** at least one selected card uses lot or serial tracking or has lot or serial records
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked without modifying either card

#### Scenario: Reject current stock or reservations
- **GIVEN** either selected card has a non-zero on-hand quantity or reserved quantity in any location, package, owner, or company
- **WHEN** the consolidation preview is evaluated or confirmation is attempted
- **THEN** consolidation is blocked and the remaining stock or reservation is reported

#### Scenario: Revalidate before confirmation
- **GIVEN** an eligible preview has already been generated
- **WHEN** product or operational data changes before confirmation and makes the pair ineligible
- **THEN** confirmation is refused using the current data and no partial consolidation is applied

### Requirement: Deterministic canonical data

The canonical card SHALL remain the source of truth for scalar product properties, while compatible relational configuration from the duplicate SHALL be retained without creating duplicate configuration records.

#### Scenario: Preserve canonical scalar values
- **GIVEN** the canonical and duplicate cards contain different names, descriptions, images, prices, costs, or accounting properties
- **WHEN** consolidation succeeds
- **THEN** the canonical card keeps its scalar values and the preview makes this policy visible before confirmation

#### Scenario: Combine non-conflicting configuration
- **GIVEN** the duplicate contains supplier references, price rules, routes, taxes, tags, packaging, or replenishment configuration that does not conflict with canonical configuration
- **WHEN** consolidation succeeds
- **THEN** the supported configuration remains available for the canonical card without duplicate equivalent records

#### Scenario: Block unresolved configuration conflicts
- **GIVEN** equivalent canonical and duplicate configuration records carry incompatible business values
- **WHEN** the consolidation preview is evaluated
- **THEN** consolidation is blocked and each conflict is identified for manual resolution

### Requirement: State-aware reference handling

The system SHALL redirect only references whose business documents are still editable drafts and SHALL preserve confirmed, completed, cancelled, posted, and otherwise immutable operational history on the duplicate card.

#### Scenario: Redirect eligible draft documents
- **GIVEN** editable draft sales or purchase documents reference the duplicate card
- **WHEN** consolidation succeeds
- **THEN** their product lines reference the canonical card and retain their entered quantities, units, descriptions, prices, taxes, and discounts

#### Scenario: Preserve non-draft history
- **GIVEN** confirmed, completed, cancelled, posted, returned, or otherwise non-editable documents reference the duplicate card
- **WHEN** consolidation succeeds
- **THEN** those references and their business values remain unchanged

#### Scenario: Open historical source product
- **GIVEN** a preserved historical document references a consolidated duplicate
- **WHEN** a permitted user opens the referenced product card
- **THEN** the archived card remains accessible and identifies its canonical card

### Requirement: Duplicate retirement and future resolution

After successful consolidation, the system SHALL retire the duplicate card, record its canonical relationship, and resolve supported former identifiers to the canonical product for future operations.

#### Scenario: Archive the duplicate
- **WHEN** consolidation succeeds
- **THEN** the canonical card remains active, the duplicate is archived, and the duplicate records which canonical card replaced it

#### Scenario: Prevent accidental reactivation
- **GIVEN** a duplicate card has been consolidated and archived
- **WHEN** a user attempts to reactivate it without reversing the consolidation through a supported process
- **THEN** reactivation is refused and the canonical relationship remains unchanged

#### Scenario: Resolve an alternative internal reference
- **GIVEN** the duplicate had an internal reference that is not the canonical card's current internal reference
- **WHEN** a backend product lookup or purchase-line import searches by that former reference
- **THEN** the canonical product is returned and no new duplicate is planned

#### Scenario: Resolve an alternative barcode
- **GIVEN** the duplicate had a barcode that is not the canonical card's current barcode
- **WHEN** a supported backend lookup or purchase-line import searches by that former barcode
- **THEN** the canonical product is returned without changing the canonical barcode

#### Scenario: Preserve supplier product resolution
- **GIVEN** a supplier identifier previously resolved to the duplicate product
- **WHEN** a later purchase-line import for the same supplier uses that identifier
- **THEN** it resolves to the canonical product unless a reported supplier configuration conflict prevents consolidation

#### Scenario: Consolidate another duplicate later
- **GIVEN** an active canonical card has already absorbed one duplicate
- **WHEN** it is later selected with another eligible active duplicate
- **THEN** the system permits a new consolidation and retains all previously recorded alternative identifiers

### Requirement: Authorization, audit, and atomicity

Consolidation MUST be restricted, explicitly confirmed, auditable, and atomic.

#### Scenario: Reject an unauthorized user
- **WHEN** a user without product-consolidation permission attempts to preview or confirm consolidation through the user interface or server API
- **THEN** access is denied and no product data is changed

#### Scenario: Confirm an irreversible action
- **GIVEN** the preview has no blockers
- **WHEN** the user requests consolidation
- **THEN** the system requires explicit final confirmation that the duplicate will be archived

#### Scenario: Record a successful consolidation
- **WHEN** consolidation succeeds
- **THEN** the canonical card records who performed it, when it occurred, and which duplicate was consolidated

#### Scenario: Roll back a failed consolidation
- **GIVEN** any validation or write fails during consolidation
- **WHEN** the operation ends with an error
- **THEN** all changes from that attempt are rolled back and both cards remain in their pre-attempt state

#### Scenario: Retry after a failed attempt
- **GIVEN** a previous consolidation attempt failed without partial changes
- **WHEN** the blocking cause is resolved and an authorized user retries
- **THEN** the system revalidates current data and can complete the consolidation once

### Requirement: Unchanged standard product behavior

The system SHALL preserve standard product behavior for cards that have not been consolidated and for workflows that do not use alternative identifiers.

#### Scenario: Use an ordinary product
- **GIVEN** a product has neither been consolidated nor registered as a canonical target
- **WHEN** users search, buy, sell, stock, archive, unarchive, import, or report that product without invoking consolidation
- **THEN** standard Odoo behavior remains unchanged
