## MODIFIED Requirements

### Requirement: Planned sales price and upward rounding
For an initialized eligible line, the system SHALL allow the user to enter a planned sales price directly. The system SHALL preserve the exact manually entered value without changing the line markup or any other calculated value. Subsequent changes to the effective-purchase-price basis SHALL NOT change a manually entered planned sales price. Invoking Fill Current Prices SHALL clear the manual value and restore the automatically calculated and upward-rounded planned sales price. An uninitialized line SHALL NOT accept a usable manual planned sales price or offer a price-update action.

#### Scenario: Round upward to a whole-price step
- **GIVEN** an initialized line has an unrounded planned sales price of `121` and a rounding step of `10`
- **WHEN** the planned sales price is calculated
- **THEN** it equals `130`

#### Scenario: Preserve an exact multiple
- **GIVEN** an initialized line has an unrounded planned sales price of `120` and a rounding step of `10`
- **WHEN** the planned sales price is calculated
- **THEN** it remains `120`

#### Scenario: Round upward to a fractional step
- **GIVEN** an initialized line has an unrounded planned sales price of `12.341` and a rounding step of `0.10`
- **WHEN** the planned sales price is calculated
- **THEN** it equals `12.40`

#### Scenario: Enter a planned sales price directly
- **GIVEN** an initialized line has an effective purchase price of `100`
- **AND** the configured rounding step is `0.01`
- **WHEN** the user enters a planned sales price of `12`
- **THEN** the planned sales price remains exactly `12`
- **AND** the line markup remains unchanged
- **AND** no product price is changed by editing the line

#### Scenario: Preserve a manual price after the purchase-price basis changes
- **GIVEN** a user entered a planned sales price of `12`
- **WHEN** the unit price, discount, taxes, purchase unit, currency, company, or order date changes
- **THEN** the planned sales price remains exactly `12`
- **AND** the line markup remains unchanged by the manual sales-price entry

#### Scenario: Restore automatic calculation explicitly
- **GIVEN** a line has a manually entered planned sales price
- **WHEN** the user invokes Fill Current Prices
- **THEN** the manual planned sales price is cleared
- **AND** the planned sales price is calculated from the refreshed markup and effective purchase price
- **AND** the configured upward rounding rule is applied

#### Scenario: Keep automatic calculation when manual entry is not used
- **GIVEN** an initialized eligible line has not received a manual planned sales price
- **WHEN** its effective-purchase-price basis changes
- **THEN** the system continues to calculate and round the planned sales price from the existing line markup

#### Scenario: Do not calculate from an absent snapshot
- **GIVEN** an eligible line has not been filled with current prices
- **WHEN** the user edits its commercial terms
- **THEN** the line remains uninitialized
- **AND** it does not offer a usable manual planned sales price or a product-price update
