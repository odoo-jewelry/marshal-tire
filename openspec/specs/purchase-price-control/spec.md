# Purchase Price Control Specification

> [!abstract] Контроль закупочных и продажных цен
> Позволяет закупщикам видеть расчётные показатели цены и явно сохранять закупочную и продажную цены товара при подтверждении заказа.
>
> **Использование:**
>
> В `Purchase > Configuration > Settings` добавлен блок Price Control с полями наценки по умолчанию и шага округления продажной цены для каждой компании. Стандартные поля настроек не изменялись и не удалялись.
>
> В форме запроса коммерческого предложения и заказа на закупку в товарных строках добавлены текущая справочная закупочная цена, текущая продажная цена, наценка, эффективная закупочная цена, плановая продажная цена и флажок `Save Prices`. При подтверждении заказа система сохраняет рассчитанные значения только для отмеченных товарных строк; секции, подсекции, заметки и авансовые строки не участвуют.
>
> Основные сценарии: сравнение текущих и плановых цен до подтверждения; применение company-specific наценки и округления; сохранение цен выбранных строк при обычном подтверждении или переходе в To Approve; повторное применение после возврата заказа в draft. Неотмеченные строки сохраняют стандартное поведение Odoo, отмена заказа не откатывает уже сохранённые цены, а дубликат заказа очищает флажки.
^feature-card

## Purpose

Provide purchase users with a company-aware reference purchase price, markup visibility, and an explicit way to update reference purchase and sales prices when confirming a purchase order.

## Requirements

### Requirement: Company price-control configuration

The system SHALL provide each company with a default markup percentage and a positive sales-price rounding step in the Purchase settings. The initial rounding step SHALL be `0.01`, and the initial default markup SHALL be `0%`.

#### Scenario: Configure price control for one company

- **WHEN** an administrator saves a default markup of `25%` and a rounding step of `10` for a company
- **THEN** purchase price calculations for that company use those values
- **AND** another company's configuration remains unchanged

#### Scenario: Reject a non-positive rounding step

- **WHEN** an administrator attempts to save a rounding step equal to or below zero
- **THEN** the system rejects the configuration with a validation message

### Requirement: Independent reference purchase price

The system SHALL maintain `last_purchase_price` for each product variant and company in the company's currency and the product's base unit of measure. This value SHALL be independent of inventory valuation cost.

#### Scenario: Different reference prices by company

- **GIVEN** the same product is available in two companies
- **WHEN** its reference purchase price is updated in one company
- **THEN** the reference purchase price in the other company remains unchanged

#### Scenario: Inventory valuation remains unchanged

- **WHEN** a reference purchase price is saved for a product using Standard Price, AVCO, or FIFO
- **THEN** the product inventory valuation cost and lot valuation costs remain unchanged

### Requirement: Purchase-line price-control information

For every product line in a draft or sent purchase order, the system SHALL display the current reference purchase price, current sales price, current markup percentage, effective purchase price, planned sales price, and a per-line Save Prices option. Section, subsection, note, and down-payment lines SHALL NOT participate in price control.

#### Scenario: Display markup based on a saved reference price

- **GIVEN** a product has a reference purchase price of `100` and a current sales price of `150`
- **WHEN** the product is selected on a purchase order line
- **THEN** the current markup is displayed as `50%`

#### Scenario: Use the default markup without a reference price

- **GIVEN** a product has no positive reference purchase price and the company default markup is `30%`
- **WHEN** the product is selected on a purchase order line
- **THEN** the displayed current markup is `30%`
- **AND** the planned sales price is calculated using `30%`

#### Scenario: Ignore non-product lines

- **WHEN** a purchase order contains a section, subsection, note, or down-payment line
- **THEN** that line does not offer price saving and does not update any product price

### Requirement: Effective purchase price calculation

The effective purchase price SHALL represent one product base unit, including the selected purchase taxes and the line discount. It SHALL be converted from the purchase order currency to the company currency using the order date and company exchange-rate rules.

#### Scenario: Apply discount and taxes

- **GIVEN** a line unit price of `100`, a line discount of `10%`, and purchase taxes totaling `20%`
- **WHEN** the effective purchase price is calculated
- **THEN** it equals `108` before currency and unit-of-measure conversion

#### Scenario: Convert purchase unit and currency

- **GIVEN** the purchase line uses a purchase unit different from the product base unit and a currency different from the company currency
- **WHEN** the effective purchase price is calculated
- **THEN** the displayed value is the tax-included discounted price per product base unit in company currency

#### Scenario: Recalculate after commercial terms change

- **WHEN** the product, unit price, discount, taxes, purchase unit, order currency, company, or order date changes before confirmation
- **THEN** the effective purchase price and dependent planned sales price reflect the changed terms

### Requirement: Planned sales price and upward rounding

The system SHALL calculate the unrounded planned sales price as the effective purchase price multiplied by one plus the current markup percentage. It SHALL round any positive result upward to the nearest multiple of the configured rounding step.

#### Scenario: Round upward to a whole-price step

- **GIVEN** an unrounded planned sales price of `121` and a rounding step of `10`
- **WHEN** the planned sales price is calculated
- **THEN** it equals `130`

#### Scenario: Preserve an exact multiple

- **GIVEN** an unrounded planned sales price of `120` and a rounding step of `10`
- **WHEN** the planned sales price is calculated
- **THEN** it remains `120`

#### Scenario: Round upward to a fractional step

- **GIVEN** an unrounded planned sales price of `12.341` and a rounding step of `0.10`
- **WHEN** the planned sales price is calculated
- **THEN** it equals `12.40`

### Requirement: Explicit price saving on confirmation

When a purchase order is confirmed, the system SHALL recalculate the price-control values server-side and, for each eligible line whose Save Prices option is selected, save the effective purchase price as the product's company reference purchase price and the rounded planned sales price as its sales price. Unselected lines SHALL preserve standard Odoo confirmation behavior without changing product prices.

#### Scenario: Save an explicitly selected line

- **GIVEN** a draft purchase order line has Save Prices selected
- **WHEN** the purchase order is confirmed
- **THEN** the product reference purchase price and sales price are updated from the recalculated line values
- **AND** standard purchase-order confirmation continues

#### Scenario: Do not save an unselected line

- **GIVEN** a draft purchase order line does not have Save Prices selected
- **WHEN** the purchase order is confirmed
- **THEN** neither the reference purchase price nor the sales price is changed by price control
- **AND** standard purchase-order confirmation remains unchanged

#### Scenario: Confirmation enters approval workflow

- **GIVEN** a purchase order requires manager approval and an eligible line has Save Prices selected
- **WHEN** the user confirms the order and it enters the To Approve state
- **THEN** the selected line's prices are saved at that confirmation event
- **AND** later approval does not apply the same line again

#### Scenario: Multiple selected lines target the same sales-price owner

- **GIVEN** multiple selected lines refer to the same product or to variants sharing one sales-price owner
- **WHEN** the purchase order is confirmed
- **THEN** the lines are applied sequentially in purchase-order line order
- **AND** the last applied line determines the final shared sales price

#### Scenario: Failed confirmation is atomic

- **GIVEN** price saving or standard purchase confirmation fails
- **WHEN** the transaction is rolled back
- **THEN** neither partial product-price updates nor a partial order confirmation remain

### Requirement: Lifecycle and copied orders

The system SHALL limit price saving to the confirmation transition from Request for Quotation or RFQ Sent. Cancelling a confirmed order SHALL NOT revert saved product prices, and a copied order SHALL start with Save Prices cleared on every line.

#### Scenario: Cancel a confirmed order

- **GIVEN** selected prices were saved during confirmation
- **WHEN** the purchase order is later cancelled
- **THEN** the saved reference purchase and sales prices remain unchanged

#### Scenario: Copy a purchase order

- **WHEN** a purchase order containing selected Save Prices options is duplicated
- **THEN** the copied order has Save Prices cleared on all lines

#### Scenario: Confirm again after resetting to draft

- **GIVEN** a confirmed order is reset to draft and its Save Prices option remains selected
- **WHEN** it is confirmed again
- **THEN** current values are recalculated and applied as a new confirmation event

### Requirement: Product write authorization

Price saving SHALL use the confirming user's product write permissions and SHALL NOT bypass company or access restrictions.

#### Scenario: User cannot update the product

- **GIVEN** a confirming user lacks permission to update an affected product
- **WHEN** the user confirms an order with Save Prices selected
- **THEN** confirmation fails with an access error
- **AND** no selected product is partially updated
