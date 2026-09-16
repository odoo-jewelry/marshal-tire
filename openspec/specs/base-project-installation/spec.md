# Project Application Installation Specification

> [!abstract] Установка возможностей проекта через Tire
> Подключает все возможности проекта при установке основного приложения с сохранением существующих документов и назначенных прав доступа.
>
> **Использование:**
>
> В меню «Приложения» администратор устанавливает «Tire». Вместе с ним становятся доступны импорт закупок, управление закупочными ценами, объединение карточек товаров, пересчёт себестоимости кассовых продаж, работа с долгами покупателей и исправление чеков. Отдельно устанавливать каждую из этих возможностей не требуется; доступ к действиям определяется правами пользователя.
>
> Если в установленном приложении появились новые обязательные возможности, обновление «Tire» подключает недостающие модули. Например, работа с долгами и исправление чеков становятся доступны после обновления основного приложения, при этом прежние продажи, оплаты и бухгалтерские документы сохраняются. При русском языке интерфейса применяются предусмотренные для этих возможностей русские подписи и сообщения.
^feature-card

## Purpose

Make the complete set of project capabilities available through installation or upgrade of the main Tire application, including existing Russian translations, without separate installation of each feature or changes to historical business documents.

## Requirements

### Requirement: Complete project installation through Tire

The `tire` application SHALL include every delivered project feature module in its required dependency closure. This SHALL include `purchase_import`, `purchase_price_control`, `product_card_consolidation`, `pos_cost_recompute`, `pos_customer_debt`, and `pos_order_correction`. Installing `tire` SHALL install these modules without separate feature-installation actions. Upgrading an existing `tire` installation SHALL install any newly required module that is still uninstalled. Feature availability SHALL remain subject to its access permissions and business eligibility rules; installation SHALL NOT make an ineligible order correctable or generate financial or stock operations for historical orders.

#### Scenario: S01 Install all project capabilities together
- **GIVEN** the delivered project modules are available and Tire is not installed
- **WHEN** an administrator installs `tire`
- **THEN** Tire and all delivered project feature modules are installed
- **AND** users can access the resulting features according to their permissions without installing those modules individually

#### Scenario: S02 Add missing capabilities to an existing installation
- **GIVEN** Tire is installed but the customer debt and order correction modules are not installed
- **WHEN** an administrator upgrades `tire` with the complete project dependencies available
- **THEN** both missing modules are installed automatically
- **AND** existing orders, payments, stock operations and accounting documents are preserved

### Requirement: Installation with supplied Russian translations

Installation and upgrades of the project modules SHALL succeed when Russian is an active database language. Supplied Russian translations SHALL load and apply to their corresponding interface labels and server messages. This requirement SHALL preserve existing translations without requiring every untranslated source term to receive a new translation.

#### Scenario: S03 Install or upgrade with Russian active
- **GIVEN** Russian is an active database language
- **WHEN** the customer debt and order correction modules are installed or upgraded through the project application
- **THEN** translation loading completes without aborting the operation
- **AND** the supplied Russian translations remain available

#### Scenario: S04 Display supplied Russian interface labels
- **GIVEN** a user uses the Russian interface and has permission to view customer debts and correct eligible completed orders
- **WHEN** the user opens the debt list or an eligible order's correction interface
- **THEN** labels and messages with supplied Russian translations are shown in Russian
- **AND** translation loading does not change access permissions or correction eligibility
