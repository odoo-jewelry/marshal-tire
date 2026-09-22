## Purpose

Allow the explicit purchase tax-inclusion and historical cost correction to process goods with inventory tracking disabled when their actual valuation history is complete and provable.

## ADDED Requirements

### Requirement: Eligibility based on actual valuation evidence

The purchase correction SHALL accept goods with inventory tracking disabled when their fully received purchases and actual stock history satisfy the existing historical FIFO conditions. The inventory-tracking setting alone MUST NOT reject the selection or silently exclude its lines. The operation SHALL retain two-decimal HALF-UP rounding, unchanged discounts and removal of the converted line taxes. It MUST NOT enable inventory tracking or create quantities to obtain eligibility. Services and advance-payment lines remain outside this extension. A purchase unit different from the product base unit SHALL remain unsupported and SHALL have a separate diagnostic identifying the purchase and product.

#### Scenario: N01 Correct the package receipt with inventory tracking disabled
- **GIVEN** eligible goods have inventory tracking disabled, a fully received purchase of 50 units at 10 with an excluded 20 percent tax, a completed receipt valued at 500 and a matching internal quantity of 50
- **WHEN** the correction is applied
- **THEN** the purchase unit price becomes 12, its taxes are empty, the receipt value becomes 600 and the current unit cost becomes 12
- **AND** inventory tracking remains disabled and quantities, movement identities, dates and states remain unchanged

#### Scenario: N02 Process a mixed purchase without silently skipping goods
- **GIVEN** a selection contains eligible goods with inventory tracking both enabled and disabled
- **WHEN** the correction is applied
- **THEN** all eligible taxed lines and their affected histories are corrected atomically and included in the reported counts

#### Scenario: N03 Identify an unsupported purchase unit separately
- **GIVEN** a selected goods line uses a unit different from the product base unit
- **WHEN** correction is requested
- **THEN** the entire request is rejected with the purchase, product and unit mismatch identified
- **AND** the message does not attribute the refusal to disabled inventory tracking

#### Scenario: N04 Identify an unsupported line type separately
- **GIVEN** a selected purchase contains a service or advance-payment line
- **WHEN** correction is requested
- **THEN** the request is rejected with its unsupported line type and purchase identified, without partial changes

### Requirement: Complete historical evidence remains mandatory

Goods with inventory tracking disabled SHALL use the existing historical receipt, issue, return and shortage rules only after complete accessible movement history reconciles with the recorded internal quantity. The operation SHALL inspect all required history and MUST NOT infer its completeness from the tracking setting or from the mere existence of a receipt. Missing or incomplete receipts, unreconciled quantities and unsupported flow structures SHALL produce a specific atomic refusal. Such a refusal SHALL identify an unsupported historical valuation basis rather than claim that every non-inventory good is invalid. The operation MUST NOT invent stock, silently perform only a price change, or substitute current product cost for missing historical evidence.

#### Scenario: N05 Refuse an unprovable history with a concrete reason
- **GIVEN** goods with inventory tracking disabled have missing or incomplete receipt evidence, or their actual movements do not reconcile with their recorded internal quantity
- **WHEN** correction is requested
- **THEN** the entire request is rejected with the product and the missing or inconsistent valuation evidence identified
- **AND** no price, tax, quantity or cost is changed

#### Scenario: N06 Preserve the historical order of different receipt costs
- **GIVEN** eligible goods with inventory tracking disabled have a corrected receipt at unit cost 120, an intervening issue and a later unselected receipt at unit cost 200
- **WHEN** the correction is applied
- **THEN** the earlier issue uses its proven historical cost of 120 and later issues consume the available receipts in historical FIFO order
- **AND** the unselected receipt keeps its recorded value and today's product cost does not replace an earlier source

### Requirement: Explicit historical POS costs for proven sources

Within the explicit purchase correction, every affected supported paid or completed POS line for eligible goods with inventory tracking disabled SHALL derive its cost from its proven completed movements. Sales and linked refunds SHALL retain their correct cost signs and standard order-date currency conversion. This explicit historical result SHALL take precedence over using the current product-card cost for those selected lines. Earlier POS lines outside the affected interval SHALL retain their saved costs. Missing, ambiguous, incomplete or protected sources SHALL reject the whole correction; there SHALL be no fallback to today's product cost. This extension MUST NOT change the ordinary POS cost policy outside the explicit correction.

#### Scenario: N07 Recompute a sale and linked refund from historical movements
- **GIVEN** eligible goods with inventory tracking disabled have an affected one-unit sale and linked refund whose proven corrected source cost is 120, while a later receipt makes the current product cost different
- **WHEN** the purchase correction is applied
- **THEN** the sale cost becomes 120 and the refund cost becomes -120, with corresponding margins
- **AND** the ordinary receipt, payment, revenue and session facts are unchanged

#### Scenario: N08 Preserve the earlier original sale of a later refund
- **GIVEN** a supported affected refund originates from a sale before the earliest corrected receipt
- **WHEN** the correction is applied
- **THEN** the refund uses the unchanged original issue value and the earlier sale's saved cost remains unchanged

#### Scenario: N09 Reject a POS dependency without proven valuation evidence
- **GIVEN** an affected POS line for goods with inventory tracking disabled has missing, unfinished or ambiguous stock sources
- **WHEN** correction is requested
- **THEN** the entire request is rejected with that POS dependency identified, without substituting current product cost or retaining a partial correction

### Requirement: Preserve the explicit action lifecycle and protections

The extension SHALL retain the existing action's permissions, company isolation, financial and protected-history restrictions, atomicity, serialization and retry behavior. Opening or cancelling the dialog SHALL remain free of business changes. Ordinary writes, copying, imports and module upgrades MUST NOT trigger the historical correction. No separate journal, persistent correction flag or manual financial override SHALL be introduced. Client-supplied context MUST NOT authorize historical POS valuation for unvalidated lines or another company.

#### Scenario: N10 Cancel before application
- **WHEN** a user opens and cancels the existing correction dialog for a purchase containing goods with inventory tracking disabled
- **THEN** its prices, taxes, costs and tracking settings remain unchanged

#### Scenario: N11 Repeat a successful mixed correction
- **GIVEN** an eligible mixed selection has already been corrected
- **WHEN** the user applies the action again without new positive taxes
- **THEN** the action reports no further corrections and no price or valuation changes occur

#### Scenario: N12 Roll back a late POS failure
- **GIVEN** a mixed correction has already changed purchase and stock values within its attempt
- **WHEN** a required POS cost update fails
- **THEN** all changes from that attempt are rolled back and a later retry starts from the unchanged facts

#### Scenario: N13 Preserve permissions and company boundaries
- **WHEN** a caller lacks the required source access or supplies context attempting to authorize unrelated POS lines or another company
- **THEN** the caller cannot obtain unauthorized historical costs or updates, and the existing permission and company restrictions still apply

#### Scenario: N14 Detect a concurrent change to eligibility or sources
- **GIVEN** inventory-tracking configuration or a required purchase, movement or POS source changes concurrently with correction
- **WHEN** the correction would otherwise use the older facts
- **THEN** it uses a consistent current state or rejects the attempt for retry without partial values

#### Scenario: N15 Preserve ordinary behavior outside the explicit action
- **WHEN** goods with inventory tracking disabled are processed through ordinary purchase or POS operations, copying, import or a module upgrade without applying the correction
- **THEN** standard cost behavior and tracking settings remain unchanged and the new historical correction does not run automatically

#### Scenario: N16 Preserve financial and protected-history restrictions
- **GIVEN** the selected goods have a supplier bill, locked period, protected valuation or merged product history that the existing correction does not support
- **WHEN** correction is requested
- **THEN** the existing explained refusal and complete rollback remain in effect regardless of inventory tracking being disabled
