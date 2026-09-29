# Dynamic Product Stock Turnover Report Specification

> [!abstract] Динамический отчёт об обороте товаров
> Отчёт показывает остатки, движение и стоимость товаров в выбранных разрезах.
>
> **Использование:**
>
> Отчёт доступен из Dynamic Financial Reports и раздела отчётов Inventory. Пользователь выбирает компанию, период, товары, категории, склады и места хранения, настраивает группировки и колонки входящих и исходящих операций. В режиме поступлений отчёт показывает FIFO-поступления, связанные заказы на закупку и распределение расхода. Строки можно раскрывать до исходных событий, а полный результат выгружать в XLSX. Для недоступных или неоднозначных данных отчёт показывает диагностику.
^feature-card

## Purpose
TBD: Add a concise statement of this capability's purpose.

## Requirements

### Requirement: Integrated report entry points

The system SHALL provide the statement inside Dynamic Financial Reports using the installed reporting module and its shared XLSX delivery mechanism. Inventory managers SHALL also have an Inventory reporting entry to the same statement without receiving additional accounting permissions. Existing financial reports SHALL retain their permissions.

#### Scenario: S01 Open the integrated statement
- **WHEN** an inventory manager with financial reporting access opens the new statement from Dynamic Financial Reports
- **THEN** inventory dimensions, period filters, quantity and cost measures are available

#### Scenario: S02 Enter without accounting permissions
- **GIVEN** an inventory manager has no accounting reporting permissions
- **WHEN** the user opens the statement from Inventory reporting
- **THEN** the same statement is available without granting access to other financial reports

### Requirement: Scope and eligible products

The statement SHALL require one authorized company and an inclusive calendar period in the user's timezone. Defaults SHALL be the current company and the current month through today. Compatible product, category, warehouse, location and receipt selections SHALL intersect. Future end dates and incompatible selections SHALL be rejected. Location descendants SHALL be included by default and MAY be excluded explicitly. Category selections SHALL include descendant categories. Only inventory-tracked goods and company-owned valued stock SHALL contribute, including archived products with relevant activity or balances. Foreign-owned stock and direct supplier-to-customer flows outside company stock SHALL NOT contribute.

#### Scenario: S03 Apply a company and period scope
- **WHEN** the user opens the statement and narrows it by product and category
- **THEN** the default company and current-month period are shown and both product filters constrain the result

#### Scenario: S04 Reject invalid filters
- **WHEN** a request contains reversed dates, a future end date, an unauthorized company, or a location outside its selected warehouse
- **THEN** the request fails before returning report data

#### Scenario: S05 Select inventory-tracked goods only
- **GIVEN** the selection contains tracked goods, archived tracked goods with a balance, services, goods without inventory tracking, and third-party stock
- **WHEN** the statement is generated
- **THEN** only owned inventory-tracked goods and relevant archived goods contribute

### Requirement: Configurable row dimensions

Users SHALL choose and reorder unique row dimensions. Stock mode SHALL support warehouse, location, product and product category. Receipt mode SHALL support FIFO receipt, product and product category at company scope. The default SHALL be stock mode grouped by product. Both modes SHALL support operation columns. Current category and warehouse membership SHALL be used and disclosed for historical periods. Valued locations outside a warehouse SHALL remain visible in a no-warehouse group.

Receipt mode SHALL NOT combine receipt grouping or receipt/PO filters with warehouse or location filters or dimensions. The interface SHALL explain the incompatibility and require explicit removal of conflicting selections; requests SHALL NOT silently ignore them. Receipt and PO filters SHALL remain available when receipt rows are rolled up by product or category.

#### Scenario: S06 Reorder grouping dimensions
- **WHEN** the user changes warehouse/category/product grouping to category/warehouse/product
- **THEN** the nesting changes while the filtered quantities and monetary totals remain the same

#### Scenario: S07 Keep receipt analysis at company scope
- **GIVEN** warehouse grouping or a location filter is active
- **WHEN** the user selects receipt mode
- **THEN** the conflict is explained and the receipt request requires removal of spatial selections
- **AND** a direct conflicting request is rejected

### Requirement: Quantities and reporting boundaries

Quantities SHALL use completed stock events and the product's base unit. Opening balance SHALL precede the first selected day; closing balance SHALL include the final selected day, limited by a fixed generation cutoff for today. Mixed-unit totals SHALL be separated by unit. Changing row order or pagination SHALL NOT change boundaries or totals. Opening quantity plus signed period movement SHALL equal closing quantity; inconsistent source history SHALL be identified without invented stock adjustments.

#### Scenario: S08 Respect local day boundaries
- **GIVEN** completed movements occur just before and exactly at the start of a local reporting day
- **WHEN** that day is selected
- **THEN** the first belongs to opening stock and the second belongs to period movements exactly once

#### Scenario: S09 Normalize and separate quantities
- **GIVEN** one product moves two packs of six units and another is measured in kilograms
- **WHEN** their category is aggregated
- **THEN** the first contributes twelve base units and unit and kilogram totals remain separate

#### Scenario: S10 Exclude incomplete and cancelled movements
- **WHEN** history includes completed, draft, reserved, partly completed and cancelled operations
- **THEN** only their actually completed quantities contribute

#### Scenario: S11 Reconcile stock balances
- **GIVEN** opening stock is ten units, completed receipts are five units and issues are eight units
- **WHEN** the period is generated
- **THEN** closing stock is seven units and the quantity equation is satisfied

### Requirement: Spatial movements and aggregation

Stock mode SHALL attribute quantities to actual source and destination locations. An internal movement SHALL contribute an issue to its source group and a receipt to its destination group, with one shared transfer value. At a node containing both sides it SHALL have zero signed movement and SHALL NOT inflate external incoming or outgoing turnover. Gross incoming/outgoing subtotals SHALL be calculated for the node's boundary rather than by adding internal transfers from its children. Split operations SHALL use actual completed detail quantities.

#### Scenario: S12 Aggregate an internal transfer
- **GIVEN** three units move from A to B within one warehouse
- **WHEN** both locations and their warehouse subtotal are displayed
- **THEN** A shows an issue of three, B shows a receipt of three, and the warehouse has zero signed movement and no external turnover from this transfer

#### Scenario: S13 Attribute a split receipt
- **GIVEN** a receipt places two units in A and three in B
- **WHEN** A is selected
- **THEN** only two units and their allocated receipt cost contribute

### Requirement: Operation classification and columns

Period movements SHALL be assigned exactly one operation type: supplier receipt, POS sale, Sales delivery, customer return, supplier return, inventory gain, inventory loss, scrap, historical stock write-off, internal transfer, or other. Classification SHALL use actual stock direction and source-document relationships; document names and sale prices SHALL NOT determine it. Historical stock-only consumption SHALL NOT be labelled a POS sale merely because it references a POS document.

Users SHALL switch between incoming/outgoing columns and operation columns. Each operation SHALL show signed quantity and signed cost: positive into the row scope, negative out of it. Opening, closing and valuation reconciliation SHALL remain separate. Netting both sides of an internal transfer SHALL NOT hide them from drill-down.

#### Scenario: S14 Separate POS and Sales issues
- **GIVEN** completed POS and Sales deliveries use the same stock picking type
- **WHEN** operation columns are enabled
- **THEN** their quantities and costs appear in separate POS sale and Sales delivery columns

#### Scenario: S15 Classify returns and adjustments
- **GIVEN** completed customer and supplier returns, inventory gain, inventory loss and scrap exist
- **WHEN** operation columns are enabled
- **THEN** every event appears once under its corresponding operation with its stock-direction sign

#### Scenario: S16 Identify historical stock-only consumption
- **GIVEN** a completed historical write-off refers to a cancelled POS source document
- **WHEN** the statement is generated
- **THEN** the consumption appears as historical stock write-off without being counted as a POS sale

#### Scenario: S17 Switch the column layout
- **WHEN** operation columns are toggled for an unchanged scope
- **THEN** the signed sum of operation quantities equals incoming minus outgoing and endpoint balances remain unchanged

### Requirement: Cost amounts and valuation reconciliation

Amounts SHALL represent inventory cost in company currency. External movements SHALL use their current recorded stock value allocated over valued owned quantity. Endpoint totals SHALL follow standard company valuation under the configured cost method. Spatial endpoint values SHALL use a disclosed proportional quantity allocation, within valuation lots where applicable. Internal transfers SHALL use the pre-event standard unit allocation, identical on both sides.

The statement SHALL separately display the monetary reconciliation needed to satisfy opening value plus signed recorded turnover plus reconciliation equals closing value. This SHALL NOT be labelled a documented revaluation unless supported by such a document. Missing valuation SHALL be distinguished from recorded zero; totals containing missing values SHALL be marked incomplete. Source costs SHALL NOT be corrected by the report.

#### Scenario: S18 Use recorded stock cost
- **GIVEN** a receipt has a stock value different from its quotation or sales price
- **WHEN** it is reported
- **THEN** its cost amount uses recorded inventory value and drill-down explains the source

#### Scenario: S19 Allocate spatial endpoint value
- **GIVEN** company stock is twenty units worth 3000 and a selected location contains ten units
- **WHEN** its endpoint is reported without lot-specific valuation
- **THEN** its value is 1500 identified as proportional valuation allocation

#### Scenario: S20 Explain a valuation residual
- **GIVEN** standard closing value differs from opening value plus recorded signed movements
- **WHEN** the statement is generated
- **THEN** the difference is visible with its operands and no fictitious stock or revaluation document is created

### Requirement: FIFO receipt identity and consumption

Receipt mode SHALL identify actual valued incoming events with receipt date, available PO reference, recorded unit cost, opening quantity/value, period receipt and consumption, and closing quantity/value. Partial receipts of one PO SHALL remain distinguishable. Identical displayed date, PO and price SHALL NOT merge different receipts. Non-purchase receipts SHALL show their source and absence of PO.

FIFO composition and consumption SHALL use the standard company FIFO basis, labelled as reconstructed valuation attribution. Consumption spanning supported receipts SHALL be divided by quantities consumed from each. Its recorded value SHALL be distributed using consumed quantities multiplied by the recorded receipt unit costs as weights, preserving the source total; a zero total cost basis SHALL use an explicitly identified quantity allocation; each receipt's own incoming unit cost SHALL remain visible. Differences from receipt-price multiplication SHALL be explained through valuation reconciliation rather than concealed by changing receipt prices. All relevant receipts SHALL participate before receipt/PO filters are applied.

#### Scenario: S21 Identify partial PO receipts
- **GIVEN** one PO has two actual receipts and an inventory gain has no PO
- **WHEN** receipt rows are displayed
- **THEN** both PO receipts remain separate and the gain identifies its source without an invented PO

#### Scenario: S22 Consume several company FIFO receipts
- **GIVEN** a product receives ten units at cost 100 from PO-A and five at cost 120 from PO-B, then issues twelve units with recorded value 1240
- **WHEN** receipt mode is generated
- **THEN** consumption is attributed as ten units to PO-A and two to PO-B, with three units worth 360 remaining from PO-B
- **AND** the issue amounts are 1000 for PO-A and 240 for PO-B, totaling 1240

#### Scenario: S23 Filter after FIFO attribution
- **GIVEN** an issue consumes units from two POs
- **WHEN** the user filters receipt mode to the second PO
- **THEN** only that PO's attributed share is shown without rerunning FIFO as if the first PO did not exist

#### Scenario: S24 Ignore spatial transfers in company FIFO turnover
- **GIVEN** company-owned units move internally without leaving company valuation scope
- **WHEN** receipt mode is generated
- **THEN** the transfer creates neither another valued receipt nor consumption of a company FIFO receipt

#### Scenario: S25 Treat a customer return as a valued receipt
- **GIVEN** a customer return creates a valued incoming event linked to an earlier issue
- **WHEN** receipt mode is generated
- **THEN** the return is a distinct receipt at its recorded cost with a link to its source
- **AND** it is not silently merged into an original supplier PO receipt

### Requirement: Honest unsupported FIFO attribution

Unsupported quantities and values SHALL appear under an explicit unattributed entry with a reason, preserving product totals. Later receipts SHALL NOT be retroactively assigned as proven sources of negative-stock issues. If reconstructed allocations cannot reconcile with standard endpoints, the affected product's detailed attribution SHALL be withheld and complete measures shown as unattributed; source receipts SHALL remain accessible in drill-down. A receipt/PO-filtered result containing potentially relevant unattributed activity SHALL be marked incomplete, rather than showing the entire unattributed company balance as belonging to that PO.

Non-FIFO products SHALL remain in unfiltered receipt mode with attribution marked not applicable. Valuation lots SHALL remain an internal valuation basis and SHALL NOT replace receipt identity.

#### Scenario: S26 Report a shortage without invented receipts
- **GIVEN** an issue exceeds supported receipt stock or history cannot explain the endpoint
- **WHEN** receipt mode is generated
- **THEN** unsupported attribution is explicit and the product's quantities and recorded values remain accounted for

#### Scenario: S27 Preserve non-FIFO goods
- **GIVEN** inventory-tracked goods use average or standard costing
- **WHEN** unfiltered receipt mode is selected
- **THEN** their totals remain visible with receipt attribution marked not applicable

#### Scenario: S28 Respect valuation lots
- **GIVEN** a FIFO product is valued by lots and one incoming event contains multiple lots
- **WHEN** receipt mode is generated
- **THEN** supported lot-specific FIFO bases are combined into receipt rows without counting quantity or value twice

#### Scenario: S29 Disclose ambiguous event order
- **GIVEN** incoming and outgoing events share a timestamp and their consumption order cannot be established
- **WHEN** receipt mode is generated
- **THEN** attribution is explicitly unavailable rather than presented as proven by arbitrary ordering

### Requirement: Corrections and source access

Reports SHALL reflect the current recorded edition of historical stock values and SHALL NOT run correction tools. Report, details and export requests SHALL enforce inventory-manager access, source rights and one-company isolation. Privileged standard valuation computations SHALL NOT expose stock sources hidden by record rules. Incomplete visibility of required valuation history SHALL cause an explained refusal. Inaccessible related commercial documents SHALL NOT disclose their labels or be opened through elevated rights.

#### Scenario: S30 Reflect an applied historical correction
- **GIVEN** a permitted correction has already updated receipt and outgoing values
- **WHEN** a fresh historical statement is generated
- **THEN** it reflects those values without changing stock, POS or accounting documents

#### Scenario: S31 Refuse unauthorized direct requests
- **WHEN** a user without inventory-manager access or authorization for the company requests report data, details or XLSX directly
- **THEN** the request is denied without disclosing data

#### Scenario: S32 Refuse incomplete valuation visibility
- **GIVEN** record rules hide required stock valuation history
- **WHEN** the report is requested
- **THEN** the result is refused without revealing hidden source names or values

#### Scenario: S33 Respect commercial document access
- **GIVEN** stock movements are accessible but their related PO is not
- **WHEN** receipt details are opened
- **THEN** the report neither exposes the PO label nor bypasses its rights

### Requirement: Drill-down and repeatability

Each supported cell SHALL provide its contributing completed source events, quantities and amounts under the exact dimensions and operation selection. A result SHALL retain its cutoff and source/result revision identifier. Later details and exports SHALL revalidate access and the same revision; changed inputs SHALL require a refresh. Repeated reads SHALL NOT create persistent stock facts, change product costs or post documents.

#### Scenario: S34 Explain a matrix cell
- **WHEN** the user opens a POS-sale cell of a receipt row
- **THEN** details identify only attributed POS issues and their shares sum to that cell

#### Scenario: S35 Repeat without side effects
- **WHEN** an unchanged statement is generated, expanded and exported repeatedly
- **THEN** figures remain the same and no business records or costs change

#### Scenario: S36 Detect changed sources
- **WHEN** source quantity, cost, classification or access changes between generation and details or export
- **THEN** the old result cannot be combined with fresh details and a refresh is required

### Requirement: Complete and consistent XLSX

XLSX SHALL use the reporting module's shared download mechanism and server-calculated data for authorized filters, dimensions, columns and cutoff. It SHALL include the full result regardless of screen pagination, numeric quantity/value cells, safe text labels, units, currency and diagnostics. Client-supplied totals SHALL NOT determine output. All contributing history SHALL be included; workload restrictions SHALL be explicit refusals rather than silent truncation.

#### Scenario: S37 Export the full authorized result
- **GIVEN** the table spans pages and a download request contains altered client-side amounts
- **WHEN** XLSX is generated
- **THEN** all authorized rows and server-calculated amounts are exported with the statement's structure and diagnostics

#### Scenario: S38 Preserve large-history totals
- **GIVEN** relevant movements exceed one retrieval batch
- **WHEN** the statement and XLSX are generated
- **THEN** every contributing event is included exactly once, or an explicit workload refusal precedes any partial result

### Requirement: Safe replacement and standard behavior

The old report SHALL be removed from the installed application set after its project dependency has been removed and refreshed. Its sources and prior planning artifacts SHALL remain. Replacement SHALL preserve the installed project application and business data, and SHALL verify that unrelated modules are not selected for cascading removal. The new report SHALL not depend on the old report. Ordinary operations and existing reports SHALL retain their behavior when the extension is unused.

#### Scenario: S39 Replace the report safely
- **GIVEN** the old report is an installed dependency of the project application
- **WHEN** the documented replacement procedure is performed
- **THEN** the new report is available, the old report is uninstalled, the project application stays installed and business data is preserved
- **AND** old sources and planning files remain in the repository

#### Scenario: S40 Preserve ordinary workflows
- **WHEN** normal purchases, POS sales, Sales deliveries, inventory operations and existing financial reports are used without opening the new report
- **THEN** their standard behavior is unchanged by the extension
