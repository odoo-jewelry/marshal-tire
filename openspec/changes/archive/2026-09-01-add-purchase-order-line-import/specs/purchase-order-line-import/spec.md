## Purpose

Provide a repeatable and validated way to populate an empty draft purchase order from a supplier CSV or XLSX file while resolving or creating product variants and synchronizing supplier prices.

## ADDED Requirements

### Requirement: Import action on a draft purchase order

The system SHALL provide an order-line import action on an existing request for quotation or purchase order while it is in the draft lifecycle state and has no order lines. The action SHALL use the already entered order header and SHALL NOT import or change header values. The system MUST reject import when any product, section, or note line already exists.

#### Scenario: Open import from a draft order

- **GIVEN** a draft purchase order with a vendor and company and no order lines
- **WHEN** an authorized user starts the order-line import action
- **THEN** the system opens an import wizard linked to that purchase order
- **AND** the existing order header remains unchanged

#### Scenario: Reject import into a non-empty order

- **GIVEN** a draft purchase order containing a product, section, or note line
- **WHEN** a user attempts to start, preview, or apply an order-line import
- **THEN** the system rejects the operation without deleting or changing any existing line
- **AND** no product, variant, or supplier price is created or updated

#### Scenario: Reject import outside the draft state

- **GIVEN** a purchase order that is confirmed, locked, or cancelled
- **WHEN** a user attempts to start or apply an order-line import
- **THEN** the system rejects the operation without changing the order, products, or supplier prices

### Requirement: CSV and XLSX source configuration

The system SHALL accept CSV and XLSX files, SHALL allow an XLSX worksheet to be selected, and SHALL allow the header row and first data row to be configured independently. The first data row MUST be after the header row. XLSX row settings SHALL refer to physical 1-based worksheet rows, including blank rows. Only cells with non-empty header labels SHALL become source columns. For XLSX, the import data block SHALL end before the first fully empty physical worksheet row after the configured first data row.

#### Scenario: Parse a file with introductory rows

- **GIVEN** a valid file whose column headers are on row 4 and whose data begins on row 7
- **WHEN** the user selects those row numbers and requests parsing
- **THEN** the system uses row 4 as the column names
- **AND** only rows beginning with row 7 are presented as import data

#### Scenario: Preserve physical XLSX row numbers

- **GIVEN** an XLSX worksheet containing blank introductory rows
- **AND** its headers are on physical row 14 and its data begins on physical row 16
- **WHEN** the user configures header row 14 and first data row 16
- **THEN** the system reads those physical worksheet rows without renumbering only the non-empty rows
- **AND** preview errors report the original physical worksheet row numbers

#### Scenario: Parse merged XLSX headers

- **GIVEN** an XLSX table whose visible headers use merged cells and therefore contain unnamed physical columns
- **WHEN** the user requests parsing
- **THEN** each non-empty header anchor is offered once for mapping
- **AND** unnamed physical columns are ignored without shifting values under the named columns

#### Scenario: Stop before XLSX summaries

- **GIVEN** an XLSX data block followed by a fully empty worksheet row and then totals, taxes, or signatures
- **WHEN** the file is parsed or validated
- **THEN** only rows before the fully empty separator are treated as import data
- **AND** summary values below the separator are not presented or imported

#### Scenario: Select an XLSX worksheet

- **GIVEN** an XLSX file containing multiple worksheets
- **WHEN** the user selects a worksheet
- **THEN** parsing and preview use only the selected worksheet

#### Scenario: Reject an invalid file layout

- **WHEN** the file format is unsupported, the worksheet does not exist, the header row cannot be read, or the first data row is not after the header row
- **THEN** the system reports a validation error without changing business records

#### Scenario: Reject a file without data rows

- **WHEN** the selected data range contains no non-empty import rows
- **THEN** the system rejects the import without creating purchase order lines

#### Scenario: Reload a source file after parsing

- **GIVEN** a file has already been parsed or previewed
- **WHEN** the user replaces the file or changes its layout settings and requests reloading
- **THEN** a secondary reload action remains available without closing the wizard
- **AND** the mapping and preview are rebuilt or invalidated for the current file and settings

### Requirement: Named import profiles

The system SHALL allow named, company-scoped import profiles to store file options, header and data row positions, source-column mappings, product lookup rules, unmatched-product policy, product creation mode, and product defaults. A user SHALL be able to select an existing profile or save the current configuration as a profile.

#### Scenario: Reuse a saved profile

- **GIVEN** an import profile available to the purchase order company
- **WHEN** the user selects the profile for a new file
- **THEN** the saved parsing, mapping, lookup, and product-creation settings are applied to the wizard

#### Scenario: Save a mapping as a profile

- **WHEN** an authorized profile manager saves a valid import configuration under a unique name for a company
- **THEN** the configuration becomes available for later imports in that company

#### Scenario: Prevent cross-company profile use

- **GIVEN** a profile belonging to another company outside the user's allowed companies
- **WHEN** the user opens an import for a purchase order
- **THEN** that profile is neither selectable nor usable for the order

### Requirement: Configurable column mapping

The system SHALL allow source columns to be mapped to supported purchase-line values, product identifiers, supplier identifiers, and variant attributes. Quantity, unit price, and at least one deterministic product identifier or a complete configured variant combination MUST be available for every imported row. When standalone-product creation is enabled, product name MUST also be mapped and present for every unmatched row.

#### Scenario: Map recognized columns

- **GIVEN** a parsed file with named columns
- **WHEN** the user maps the source columns and requests validation
- **THEN** the preview displays the normalized product, quantity, unit, price, description, supplier code, and attribute values that will be applied

#### Scenario: Reject incomplete or duplicate mappings

- **WHEN** a required value is not mapped or incompatible source columns are mapped more than once to the same target
- **THEN** the system reports the mapping errors and does not enable application of the import

### Requirement: Preview without business mutations

The system SHALL validate every non-empty source row and show its source row number, normalized values, resolved product or planned creation, and errors before applying the import. Parsing and preview MUST NOT create, update, or delete purchase lines, products, variants, attributes, attribute values, or supplier prices.

#### Scenario: Preview a valid import

- **WHEN** the user validates a fully mapped file
- **THEN** each source row is shown with its resolved outcome
- **AND** the import can be applied only when all rows are valid

#### Scenario: Preview reports row-specific errors

- **GIVEN** a file containing an invalid quantity, an ambiguous product identifier, or an incompatible unit
- **WHEN** the user validates the file
- **THEN** each error identifies the source row and reason
- **AND** no business record is changed

#### Scenario: Reject application of a stale preview

- **GIVEN** a valid preview was generated
- **WHEN** the source file, mapping, profile settings, or purchase order lines change before application
- **THEN** the system requires a new validation preview
- **AND** the purchase order and related business records remain unchanged

### Requirement: Deterministic product resolution

The system SHALL resolve products by the exact, ordered lookup rules stored in the selected profile. Supported lookup keys SHALL include the current vendor's product code, internal reference, and barcode. A lookup that returns more than one valid product MUST be treated as ambiguous rather than selecting a product implicitly.

#### Scenario: Resolve by vendor product code

- **GIVEN** the profile prioritizes vendor product code and exactly one variant has that code for the purchase order vendor and company
- **WHEN** the file row is validated
- **THEN** that variant is selected for the purchase line

#### Scenario: Continue through ordered lookup keys

- **GIVEN** no product matches the first configured key and exactly one product matches a later configured key
- **WHEN** the file row is validated
- **THEN** the later exact match is selected

#### Scenario: Reject an ambiguous identifier

- **GIVEN** a configured lookup key matches multiple eligible products
- **WHEN** the file row is validated
- **THEN** the row is rejected as ambiguous
- **AND** no new product is created for that row

### Requirement: Unmatched product policy

An import profile SHALL define whether an unmatched row is rejected or creates a product. Product creation SHALL support either a new standalone product with one variant or a variant of a selected existing product template.

#### Scenario: Reject an unmatched product

- **GIVEN** the profile uses the reject policy
- **WHEN** no configured lookup key resolves a row
- **THEN** the row is invalid and the import cannot be applied

#### Scenario: Create a standalone product

- **GIVEN** the profile uses standalone-product creation
- **AND** a valid row cannot be resolved to an existing product
- **WHEN** the import is applied
- **THEN** the system creates one purchasable product with the mapped product name using mapped values, then profile defaults, then standard defaults
- **AND** the created variant is used on the new purchase line

#### Scenario: Create a variant from an existing template configuration

- **GIVEN** the profile uses variant creation and identifies an existing product template
- **AND** the row supplies one existing value for every variant-defining attribute required by that template
- **AND** the resulting valid combination does not yet exist
- **WHEN** the import is applied
- **THEN** the system creates the variant through the template's standard variant rules
- **AND** applies mapped internal reference and barcode values to the new variant
- **AND** uses the new variant on the purchase line

#### Scenario: Reuse an existing variant combination

- **GIVEN** the mapped attribute combination already identifies an active variant of the selected template
- **WHEN** the row is validated
- **THEN** the existing variant is selected and no duplicate variant is planned

#### Scenario: Reject an invalid variant combination

- **WHEN** a row omits a required variant attribute, names an unknown attribute value, uses a value not assigned to the selected template, or forms an excluded combination
- **THEN** the row is rejected
- **AND** the import does not create or modify attributes, attribute values, or template attribute lines

### Requirement: Atomic population of an empty purchase order

Applying a valid import SHALL require the draft purchase order to remain empty and SHALL atomically create the imported product lines in source-file order. The import MUST NOT delete purchase order lines. Any failure MUST leave the order empty and preserve products, variants, and supplier prices.

#### Scenario: Populate an empty order

- **GIVEN** a draft order without any product, section, or note lines
- **AND** every preview row is valid
- **WHEN** the user applies the import
- **THEN** one new product line is created for each imported data row in source order
- **AND** the purchase order header remains unchanged

#### Scenario: Roll back a failed application

- **GIVEN** an error occurs while creating a product, variant, supplier price, or purchase line
- **WHEN** the import is applied
- **THEN** the operation fails atomically
- **AND** the purchase order remains empty and products, variants, and supplier prices remain unchanged

#### Scenario: Retry after a failed application

- **GIVEN** a previous application failed without business mutations
- **WHEN** the user corrects the file or configuration and applies a valid import
- **THEN** the corrected import populates the empty order exactly once

### Requirement: Purchase prices and supplier pricelist synchronization

The imported unit price SHALL be stored on the purchase line in the purchase order currency and line unit of measure. For each imported product or variant, the system SHALL create or update the supplier price identified by the commercial vendor, concrete variant, order company, order currency, line unit of measure, and imported minimum quantity. When minimum quantity is not mapped, zero SHALL be used. Supplier code and supplier product name SHALL be updated only when supplied by mapped columns.

#### Scenario: Create a variant-specific supplier price

- **GIVEN** no supplier price exists for the exact vendor, variant, company, currency, unit, and minimum-quantity key
- **WHEN** a valid row is imported
- **THEN** the purchase line receives the imported unit price
- **AND** a supplier price with that price and exact key is created for the variant

#### Scenario: Update the matching supplier price

- **GIVEN** one supplier price exists for the exact vendor, variant, company, currency, unit, and minimum-quantity key
- **WHEN** a valid row with a different unit price is imported
- **THEN** that supplier price is updated to the imported price
- **AND** no additional supplier price is created for the key

#### Scenario: Preserve unrelated supplier price tiers

- **GIVEN** supplier prices exist for another vendor, variant, company, currency, unit, or minimum quantity
- **WHEN** a row is imported
- **THEN** those unrelated supplier prices remain unchanged

#### Scenario: Reject conflicting prices for one supplier-price key

- **GIVEN** two file rows resolve to the same supplier-price key but contain different unit prices
- **WHEN** the file is validated
- **THEN** both rows are reported as conflicting and the import cannot be applied

#### Scenario: Reject an ambiguous existing supplier-price key

- **GIVEN** multiple supplier prices already exist for the exact vendor, variant, company, currency, unit, and minimum-quantity key
- **WHEN** a matching file row is validated
- **THEN** the row is rejected as ambiguous
- **AND** none of the supplier prices is updated

### Requirement: Permissions and company isolation

The system SHALL enforce the current user's purchase-order, product, supplier-price, and profile permissions during import. Import processing SHALL NOT bypass these permissions. Profiles, selected templates, products, units, taxes, and supplier prices MUST be compatible with the purchase order company.

#### Scenario: Authorized purchase user applies an import

- **GIVEN** a user can modify the draft order and has every permission required by the selected profile's planned operations
- **WHEN** the user applies a valid import
- **THEN** the import completes within the purchase order company

#### Scenario: Missing product-management permission

- **GIVEN** an import would create a product or variant but the user lacks the required permission
- **WHEN** the user validates or applies the import
- **THEN** the operation is rejected without partial changes

#### Scenario: Reject company-incompatible data

- **WHEN** an import references a profile, template, product, unit, tax, or supplier price that is not available to the purchase order company
- **THEN** the import is rejected without changing business records

### Requirement: Preserve standard purchase behavior

The module SHALL NOT alter standard purchase-order entry, confirmation, cancellation, stock, invoicing, or supplier-price behavior unless a user explicitly applies this import action.

#### Scenario: Use a purchase order without import

- **WHEN** a user creates, edits, confirms, receives, invoices, or cancels a purchase order without applying the custom import action
- **THEN** standard Odoo behavior remains unchanged
