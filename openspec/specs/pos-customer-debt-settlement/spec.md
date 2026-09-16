# POS Customer Debt Settlement Specification

> [!abstract] Погашение долгов покупателей по кассовым заказам
> Позволяет учитывать задолженность по заказам закрытых кассовых смен и погашать её выбранными суммами входящих платежей с сохранением бухгалтерской истории.
>
> **Использование:**
>
> В меню «Point of Sale» добавлены «Customer Debts» для просмотра задолженностей и «Review Historical Debt Links» для проверки связей старых заказов. Список долгов показывает клиента, компанию, заказ, смену, дату, первоначальный долг, погашение платежами, прочие корректировки, остаток, состояние и причину проверки. Доступны поиск по клиенту и дате, фильтры «Outstanding», «Settled», «Review Required» и действие «Settle» для выбранных совместимых заказов.
>
> В обычном списке «Orders» сохраняются стандартные столбцы и их порядок, включая номер чека, клиента, итог и статус заказа, а также стандартный поиск. Для пользователей с правом просмотра долгов добавлены шесть переключаемых столбцов: первоначальный долг, погашение платежами, прочие корректировки, остаток, состояние долга и причина проверки. В «Orders» они скрыты по умолчанию и включаются через выбор столбцов; в отдельном списке «Customer Debts» показаны по умолчанию, но каждый из них можно отключить. Скрытие столбцов не меняет заказы и задолженность.
>
> В форме заказа добавлены кнопка и вкладка «Customer Debt»: состояние задолженности, первоначальная сумма, остаток, суммы погашения и корректировок, причина проверки, история распределений и доступные пользователю бухгалтерские источники. В карточке клиента добавлена кнопка «POS Debts» со счётчиком, открывающая связанные долги. Сводки относятся к кассовым долгам и разделяются по компаниям и валютам.
>
> В форме входящего платежа покупателя добавлена вкладка «POS Debt Settlement» с распределённой и доступной суммами, таблицей заказов, назначенными и действующими суммами погашения, состоянием распределения и действием «Undo». Кнопка «Apply Available Payment» применяет свободный остаток проведённого платежа. В форме регистрации платежа из долгов добавлен блок «POS Debt Distribution» с выбранными заказами и редактируемыми суммами. В изменённых формах существующие поля не изменены и не удалены.
>
> В форме «Review Historical Debt Links» выбирают заказы и выполняют «Analyze and Link»: результат показывает число проверенных, привязанных и требующих проверки заказов. Неоднозначные связи требуют отдельной проверки. Просмотр долгов и бухгалтерское погашение доступны по назначенным правам в разрешённых компаниях.
>
> Например, платёж 70 можно распределить как 20 и 50 между двумя долгами по 100: останутся долги 80 и 50. При платеже 100 и погашении 70 свободные 30 сохраняются на аккаунте клиента. Позднее выставление счёта сохраняет уже погашенные суммы; однозначный возврат на аккаунт уменьшает долг исходного заказа, а возврат наличными сам по себе его не погашает. Отмена платежа или снятие сопоставления отражаются в остатке и истории; повторное подтверждение не создаёт повторного погашения.
^feature-card

## Purpose

Provide traceable customer debt settlement for point-of-sale orders from closed sessions, with explicit allocation of incoming payments and accounting-backed balances.

## Requirements

### Requirement: Eligible customer debts

The system SHALL expose customer-account debt for completed point-of-sale orders only after their sessions are closed and the corresponding accounting documents are posted. An invoice SHALL NOT be mandatory. Eligibility SHALL use the payment method's customer-account behavior rather than its translated name.

#### Scenario: S01 Uninvoiced closed-session debt
- **GIVEN** a closed-session order for 100 with 30 paid in cash and 70 charged to an identified customer account
- **WHEN** an authorized user opens customer debts
- **THEN** the order is available with an original debt of 70 and an outstanding amount of 70 without requiring an invoice

#### Scenario: S02 Open-session exclusion
- **GIVEN** a customer-account order whose session is not closed, including an invoiced order
- **WHEN** a user attempts to settle it through the debt feature
- **THEN** settlement is unavailable and a direct request is rejected without creating a payment or reconciliation

#### Scenario: S03 Invalid customer identification
- **GIVEN** a customer-account order without reliably identified customer-specific debt
- **WHEN** its settlement eligibility is evaluated
- **THEN** it is marked as requiring review and cannot be allocated to an arbitrary customer

#### Scenario: S04 Translated payment method
- **WHEN** a customer-account payment method is renamed or translated
- **THEN** otherwise eligible debt remains identifiable

### Requirement: Debt list and customer history

The system SHALL provide a debt list with customer, company, currency, order, session, date, original debt, settlement by payments, other accounting adjustments, outstanding amount, and settlement status. It SHALL support filters by customer, date, outstanding or settled status, and review status. Order and customer forms SHALL expose the related debts and settlement history. Totals SHALL remain separated by company and currency; debt totals SHALL NOT imply the customer's full accounting balance.

#### Scenario: S05 Debt navigation
- **WHEN** a user filters outstanding debts for a customer and opens an order or that customer's debt history
- **THEN** the same eligible orders and balances are shown with links to the underlying accounting documents and payments

#### Scenario: S06 Accounting source of truth
- **GIVEN** an order with a customer-account debt of 100
- **WHEN** a payment of 40 is reconciled to that debt through a standard accounting operation
- **THEN** the debt feature shows the payment and an outstanding amount of 60 without manual balance correction

#### Scenario: S07 Settled debt history
- **WHEN** the last outstanding amount of an eligible order is settled
- **THEN** it leaves the default outstanding list but remains accessible through the settled filter and customer history

### Requirement: Explicit payment allocation

Authorized users SHALL be able to allocate an incoming customer payment to selected eligible orders of the same accounting customer, company, receivable account, and currency. Allocation amounts SHALL be explicit and positive, SHALL NOT exceed the current debt or available payment amount, and SHALL NOT cause automatic allocation to unselected orders. Draft allocations SHALL NOT reduce debt. The first version SHALL reject cross-currency allocations with a clear explanation.

#### Scenario: S08 Partial order settlement
- **GIVEN** an outstanding order debt of 100
- **WHEN** a user confirms an incoming payment allocating 40 to that order
- **THEN** exactly 40 is settled and the order retains a debt of 60

#### Scenario: S09 Exact multi-order distribution
- **GIVEN** two orders with outstanding debts of 100 each
- **WHEN** a payment of 70 is allocated as 20 to the first order and 50 to the second
- **THEN** their outstanding amounts become 80 and 50 respectively regardless of order dates

#### Scenario: S10 Unallocated payment remainder
- **GIVEN** a payment of 100 and an allocation of 70 to a selected debt
- **WHEN** the allocation is confirmed
- **THEN** 30 remains available as customer credit and is not applied to another order

#### Scenario: S11 Existing payment allocation
- **GIVEN** a posted incoming payment with an unreconciled available amount of 60
- **WHEN** a user applies 25 of that payment to an eligible order
- **THEN** the debt decreases by 25 and the same payment retains 35 available without creating another receipt of money

#### Scenario: S12 Draft payment
- **WHEN** a user saves draft payment allocations
- **THEN** order debts and accounting reconciliations remain unchanged

#### Scenario: S13 Invalid allocation amount
- **WHEN** a request contains a non-positive allocation, duplicate allocation of the same order, an amount exceeding an order's current debt, or a total exceeding the available payment amount
- **THEN** the entire request is rejected without partial settlement

#### Scenario: S14 Incompatible allocation target
- **WHEN** a request attempts to allocate an outgoing or cancelled payment, or mixes accounting customers, companies, receivable accounts, or currencies
- **THEN** the entire request is rejected with the relevant incompatibility explained

### Requirement: Payment creation from debts

The debt list SHALL offer a settlement action opening payment registration for compatible selected debts. It SHALL prefill the accounting customer, currency and selected outstanding amounts, and SHALL use the same allocation validation as the payment form.

#### Scenario: S15 Register payment from selected debts
- **WHEN** a user selects compatible outstanding orders and invokes settlement
- **THEN** payment registration opens with those orders and their current outstanding amounts, and successful confirmation produces a linked incoming payment

### Requirement: Invoice continuity

An invoiced order SHALL have one effective debt. Standard invoice payments SHALL be reflected in the order's debt. Issuing an invoice after session closure SHALL preserve existing settlement and SHALL NOT reopen an already settled amount or affect another order's debt.

#### Scenario: S16 Invoiced order
- **GIVEN** a closed-session order with 30 paid in cash and 70 charged to the customer account and a posted invoice
- **WHEN** its debt is displayed or settled
- **THEN** the effective outstanding debt is the invoice's remaining 70 and no additional session debt is counted

#### Scenario: S17 Invoice after partial settlement
- **GIVEN** an uninvoiced closed-session order with original debt 100 and a later payment of 40, and another outstanding order for the same customer in that session
- **WHEN** an invoice is issued for the partially settled order
- **THEN** that order still owes 60, its payment history remains traceable, and the other order's debt is unchanged

### Requirement: Refund accounting

The system SHALL distinguish refunds credited to the customer account from refunds paid back in cash or through a bank. A posted customer-account refund from a closed session with one unambiguous source order SHALL offset that order's outstanding debt through accounting reconciliation up to the available amount. Remaining credit SHALL stay on the customer's account. Ambiguous refunds SHALL remain identifiable for review without guessing allocation.

#### Scenario: S18 Refund to customer account
- **GIVEN** an outstanding debt of 80 and a refund of 30 credited to the customer account with one identified source order
- **WHEN** the refund session closes and its accounting documents are posted
- **THEN** the source order's debt becomes 50 and the adjustment is identified as a refund rather than money received

#### Scenario: S19 Cash refund
- **GIVEN** an outstanding order debt of 80
- **WHEN** a refund of 30 for that order is actually paid back in cash and posted
- **THEN** the debt remains 80 unless a separate accounting credit is applied to it

#### Scenario: S20 Refund exceeding debt
- **GIVEN** a remaining order debt of 20 and a customer-account refund of 50
- **WHEN** the traceable refund is posted after its session closes
- **THEN** the order debt becomes zero and the remaining 30 stays as customer credit without a negative order debt

#### Scenario: S21 Unposted refund
- **WHEN** a customer-account refund is still in an open session
- **THEN** it does not reduce an order's debt through this feature

#### Scenario: S37 Ambiguous refund
- **WHEN** a posted customer-account refund from a closed session has no unambiguous single source order
- **THEN** its credit is exposed for review without automatically reducing a selected order's debt

### Requirement: Cancellation and reconciliation lifecycle

Debt balances and active payment links SHALL follow valid accounting reconciliations. Standard cancellation, reversal, or removal of a reconciliation SHALL restore the affected amount as appropriate. Confirmed allocation history SHALL NOT act as a second monetary ledger. A posted allocation SHALL NOT be silently reassigned by editing or copying a payment.

#### Scenario: S22 Payment cancellation
- **GIVEN** an original debt of 100 partly settled by a payment of 40
- **WHEN** that payment is cancelled through a permitted standard accounting operation
- **THEN** the outstanding debt returns to 100 and the historical allocation is shown as no longer effective

#### Scenario: S23 Reconciliation removal
- **WHEN** a reconciliation applying a payment or refund to an order is removed through standard accounting
- **THEN** the debt and effective history reflect the remaining reconciliations without automatically reapplying the removed allocation

#### Scenario: S24 Payment modification
- **WHEN** a user attempts to change confirmed allocations
- **THEN** an explicit accounting undo is required before reassignment

#### Scenario: S38 Payment copy
- **WHEN** a user copies a payment carrying allocations
- **THEN** the copy carries no effective allocations or debt links

### Requirement: Atomic and repeatable settlement

Settlement SHALL validate current balances atomically and SHALL be safe against repeated confirmation and concurrent requests. Validation SHALL apply equally to interface actions, imports, and direct server requests.

#### Scenario: S25 Repeated confirmation
- **WHEN** the same saved allocation operation is confirmed again after success
- **THEN** no additional payment or reconciliation is created

#### Scenario: S26 Concurrent settlement
- **GIVEN** two users attempting to allocate 80 each against a debt of 100
- **WHEN** their operations overlap
- **THEN** at most one succeeds with that amount and the other must refresh rather than over-settle the debt

#### Scenario: S27 Transaction failure
- **WHEN** an error occurs after processing starts on one of several allocations
- **THEN** no part of that request remains posted or reconciled

#### Scenario: S28 Direct request validation
- **WHEN** an import or direct server request bypasses the form and supplies an ineligible debt or invalid allocation
- **THEN** the same restrictions reject it without financial changes

### Requirement: Access and company isolation

Debt viewing SHALL require an explicitly assigned debt-viewing permission with access to the relevant orders and companies. Settlement SHALL additionally require accounting payment permissions. New permissions SHALL NOT grant unrestricted access to accounting records. Company and customer totals SHALL only include authorized data.

#### Scenario: S29 View-only user
- **WHEN** a user with debt-viewing access but without accounting payment permissions opens eligible debts
- **THEN** permitted balances are visible but settlement and allocation mutation are denied

#### Scenario: S30 Company isolation
- **WHEN** a user accesses debt summaries, history, or settlement targets
- **THEN** records from inaccessible companies are neither exposed nor accepted through direct requests

### Requirement: Safe introduction for existing orders

Installation and upgrades SHALL preserve existing financial documents. Historical orders SHALL be linked only when the existing invoice or accounting evidence proves an unambiguous correspondence. Missing or ambiguous linkage SHALL be reported as requiring review, excluded from known-debt totals, and blocked from settlement through this feature. The system SHALL NOT guess links from amount or customer alone.

#### Scenario: S31 Unambiguous historical order
- **WHEN** historical linkage initialization encounters a closed-session order with an unambiguous existing invoice or uniquely proven receivable correspondence
- **THEN** it exposes the existing residual and payment history without new monetary entries

#### Scenario: S32 Ambiguous historical orders
- **GIVEN** multiple historical orders whose customer, amounts and session evidence do not uniquely identify their debt lines
- **WHEN** historical linkage initialization runs
- **THEN** those orders require review and their unknown residuals are not represented as zero or as confirmed amounts

#### Scenario: S33 Repeated upgrade
- **WHEN** installation initialization or a module upgrade is repeated
- **THEN** existing links are not duplicated and posted amounts and reconciliations are unchanged

### Requirement: Standard behavior preservation

The module SHALL preserve standard point-of-sale states, stock operations and payment behavior when the debt feature is not used. It SHALL operate with standard Community accounting without requiring the third-party accounting kit, and SHALL remain compatible with that kit when installed.

#### Scenario: S34 Ordinary sale and payment
- **WHEN** an ordinary cash or bank sale and a payment without debt allocations are processed
- **THEN** their standard posting, stock movement and payment behavior are unchanged

#### Scenario: S35 Optional accounting kit
- **WHEN** the debt workflow is used with standard Community accounting or with the accounting kit installed
- **THEN** eligible debts can be settled without depending on an unavailable manual-reconciliation screen

#### Scenario: S36 Order state preservation
- **WHEN** a completed customer-account order is partially or fully settled
- **THEN** its standard order state and original point-of-sale payment lines are unchanged while separate debt information reflects the settlement

### Requirement: Standard order views and optional debt columns

The ordinary Orders action SHALL retain the standard POS order list and search behavior after installation or upgrade of the debt feature. Standard columns SHALL retain their visibility and relative order, including the order reference, receipt number, customer, order total and order state. The dedicated Customer Debts list and debt-specific search SHALL be used by debt navigation without replacing the ordinary Orders views.

Users with debt-viewing permission SHALL be able to select six additional debt columns in Orders: original debt, settlement by payments, other adjustments, outstanding amount, debt state and review reason. With no saved column preferences, these columns SHALL be hidden in Orders and visible in Customer Debts. Each of these columns SHALL be independently showable and hideable through the standard column selector in both lists. Technical visibility fields SHALL NOT become selectable business columns. Changing column visibility SHALL NOT modify orders, payments or debt balances. An unknown outstanding amount SHALL remain distinguishable from a confirmed zero when its column is shown.

#### Scenario: S37 Preserve the ordinary Orders list and search
- **GIVEN** the customer debt feature has been installed or upgraded
- **WHEN** a user opens the ordinary Orders action without entering the debt workflow
- **THEN** the standard order reference, receipt number, customer, total and order state columns are available in their standard relative order
- **AND** the standard receipt-number search and order-state filters remain available instead of being replaced by debt-specific search

#### Scenario: S38 Debt columns are optional in Orders
- **GIVEN** a user has debt-viewing permission and no saved column preferences
- **WHEN** the user opens Orders
- **THEN** all six additional debt columns are hidden by default and available in the column selector
- **AND** technical visibility fields are not offered as selectable columns

#### Scenario: S39 Toggle debt columns without changing business data
- **GIVEN** a user has debt-viewing permission
- **WHEN** the user shows or hides individual debt columns in either order list
- **THEN** only the selected columns change visibility and order, payment and debt data remain unchanged
- **AND** showing the outstanding amount of an order with an unknown residual does not display that residual as a confirmed zero

#### Scenario: S40 Keep dedicated debt navigation
- **GIVEN** a user has debt-viewing permission and no saved column preferences
- **WHEN** the user opens Customer Debts or a customer's debt history
- **THEN** the dedicated debt list and its outstanding, settled and review-required filters are used
- **AND** all six debt columns are initially visible and individually hideable
- **AND** opening ordinary Orders still uses its standard list and search

#### Scenario: S41 Restrict optional debt columns to debt viewers
- **WHEN** a user without debt-viewing permission opens Orders
- **THEN** the standard order columns remain available
- **AND** the additional debt columns are not offered in the list or its column selector
