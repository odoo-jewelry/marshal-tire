## Purpose

Allow each point of sale to control whether choosing a company customer automatically requests an invoice, while retaining explicit cashier choices and standard invoicing workflows.

## ADDED Requirements

### Requirement: Per-POS automatic invoice setting

The system SHALL expose an automatic company-customer invoicing setting for each point of sale. The setting SHALL initially be disabled for newly created points of sale and for existing points of sale when the capability is first introduced. Subsequent upgrades SHALL preserve saved values. Configuration changes SHALL use existing POS configuration permissions and company restrictions.

#### Scenario: S01 New point of sale defaults to disabled
- **WHEN** an authorized user creates a new point of sale without explicitly enabling automatic company-customer invoicing
- **THEN** the setting is disabled

#### Scenario: S02 Existing point of sale starts disabled
- **WHEN** the capability is first introduced into a database containing existing points of sale
- **THEN** the setting is disabled for each existing point of sale

#### Scenario: S03 Save and retain a chosen value
- **GIVEN** an authorized user enables the setting and saves the POS configuration
- **WHEN** the settings are reopened or the module is subsequently upgraded
- **THEN** the saved enabled value is retained

#### Scenario: S04 Independent POS configuration
- **GIVEN** two points of sale have different saved values
- **WHEN** their cashier interfaces load the current settings
- **THEN** each interface uses its own value without applying the other point of sale's choice

#### Scenario: S05 Preserve configuration access restrictions
- **WHEN** a user without permission to edit a point of sale attempts to change its setting through the interface or a direct request
- **THEN** the setting remains protected by the existing configuration access and company restrictions

### Requirement: Customer selection respects the configured policy

When automatic company-customer invoicing is disabled, selecting a company customer SHALL preserve the order's current invoice choice. When enabled, selecting a company customer SHALL enable invoicing as in standard Odoo. The policy SHALL apply to each customer selection without creating an invoice at selection time. Customer assignment, pricelist selection and fiscal-position handling SHALL retain standard behavior.

#### Scenario: S06 Disabled automatic selection
- **GIVEN** the setting is disabled and the current sale has invoicing unchecked
- **WHEN** the cashier selects a company customer, including selecting that customer again
- **THEN** invoicing remains unchecked

#### Scenario: S07 Enabled standard selection
- **GIVEN** the setting is enabled and the current sale has invoicing unchecked
- **WHEN** the cashier selects a company customer
- **THEN** invoicing becomes checked as in standard Odoo

#### Scenario: S08 Preserve an explicit invoice choice
- **GIVEN** the setting is disabled and the cashier has checked invoicing manually
- **WHEN** the cashier selects or changes a company customer
- **THEN** invoicing remains checked

#### Scenario: S09 Preserve ordinary customer processing
- **WHEN** the cashier selects an individual customer with either setting value
- **THEN** the invoice choice follows standard Odoo behavior

#### Scenario: S15 Preserve customer pricing and tax effects
- **WHEN** the cashier selects an individual or company customer with either setting value
- **THEN** customer selection retains standard pricelist and fiscal-position effects

### Requirement: Invoice workflows remain explicit and compatible

The setting SHALL control automatic selection only, not permission to invoice. Cashiers SHALL retain the standard manual invoice control and its existing validation. Checkout SHALL use the order's invoice choice under standard Odoo rules. The setting SHALL NOT bypass standard invoicing requirements for refunds of invoiced sales or alter receipt-correction eligibility.

#### Scenario: S10 Manually choose invoicing at checkout
- **GIVEN** automatic company-customer invoicing is disabled and a company customer is selected
- **WHEN** the cashier chooses either invoice state using the standard control and successfully confirms an otherwise valid sale
- **THEN** an invoice is created only when requested, subject to standard validation

#### Scenario: S11 Preserve invoiced-return requirements
- **GIVEN** automatic company-customer invoicing is disabled
- **WHEN** a refund of an invoiced sale reaches the standard payment workflow
- **THEN** the standard required invoice behavior remains in effect

### Requirement: Configuration changes preserve existing documents

Introducing, saving or reloading the setting SHALL NOT modify existing order invoice choices, invoices, payments, stock movements or accounting entries. An already running cashier interface SHALL use a changed configuration after reloading current POS settings; no immediate update to other open browser tabs is required. The setting SHALL NOT impose a new invoice rule on imports or direct order requests.

#### Scenario: S12 Preserve historical and unfinished documents
- **GIVEN** the database contains unfinished orders with explicit invoice choices and completed sales with invoices and payments
- **WHEN** the capability is introduced or its configuration is changed and reloaded
- **THEN** those orders and their associated documents retain their existing values

#### Scenario: S13 Use a reloaded configuration for subsequent selection
- **GIVEN** an authorized user changes and saves the setting while a cashier interface is already open
- **WHEN** the cashier reloads current POS settings and subsequently selects a company customer
- **THEN** the selection follows the saved setting

#### Scenario: S14 Preserve direct order processing
- **WHEN** a valid order is submitted through import or a direct server request with an explicit invoice choice
- **THEN** standard server processing honors that choice independently of the automatic company-customer setting
