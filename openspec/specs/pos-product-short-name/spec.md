# POS Product Short Name Specification

> [!abstract] Сокращённое название товара в POS
> Позволяет кассиру видеть краткое название товара в каталоге POS без изменения полного названия в чеке.
>
> **Использование:**
>
> В форме товара приложения «Товары» доступно необязательное поле «Сокращение». Если оно заполнено, плитка товара в основном каталоге «Точки продаж» показывает сокращение. Если поле пусто или очищено, плитка показывает обычное полное название. При добавлении товара в заказ и печати, отправке или выводе basic-чека строка чека всегда содержит полное название и детали варианта.
^feature-card

## Purpose

Allow product maintainers to define a concise, translatable label for the POS catalog while preserving the complete product name in customer-facing receipts.

## Requirements

### Requirement: Optional product short name

The system SHALL allow users who can edit a product to save an optional, translatable short name for that product without changing its full name.

#### Scenario: Save a short name

- **GIVEN** a user is allowed to edit a product
- **WHEN** the user saves a short name on the product
- **THEN** the system retains both the short name and the unchanged full product name

#### Scenario: Leave the short name empty

- **WHEN** a product is saved without a short name
- **THEN** the product remains usable in POS without requiring any substitute value

### Requirement: Short name on the POS catalog card

The main POS product catalog SHALL display the product short name on a product card when a short name is available in the active POS language, and SHALL otherwise display the standard product name.

#### Scenario: Display a configured short name

- **GIVEN** a POS product has a short name in the active POS language
- **WHEN** the cashier views that product in the main POS catalog
- **THEN** the product card displays the short name

#### Scenario: Fall back to the standard product name

- **GIVEN** a POS product has no short name in the active POS language
- **WHEN** the cashier views that product in the main POS catalog
- **THEN** the product card displays the same standard product name used before this change

#### Scenario: Use an updated value after POS data reload

- **GIVEN** the product short name was changed after an earlier POS data load
- **WHEN** the POS reloads the current product data
- **THEN** the product card displays the current short name, or the standard product name when the short name was cleared

### Requirement: Full product name on POS receipts

The system MUST keep using the full product name, including standard variant details when applicable, for POS order-line receipt data and customer receipts regardless of whether a short name is configured.

#### Scenario: Print or send a receipt for a product with a short name

- **GIVEN** a product has a short name that is shown on its POS catalog card
- **WHEN** a cashier completes an order and prints or electronically sends its customer receipt
- **THEN** the receipt line displays the full product name rather than the short name

#### Scenario: Render a basic receipt for a product with a short name

- **GIVEN** a product has a short name that is shown on its POS catalog card
- **WHEN** POS renders the order as a basic receipt
- **THEN** the receipt line displays the full product name rather than the short name
