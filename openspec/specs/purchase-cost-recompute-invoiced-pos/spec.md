# Invoiced POS Purchase Cost Recompute Specification

> [!abstract] Пересчёт закупочной себестоимости чеков со счетами
> Позволяет пересчитать историческую себестоимость и маржу допустимых чеков со счетами покупателям, сохранив финансовые документы.
>
> **Использование:**
>
> В приложении «Закупки» выберите заказы в списке и действие «Включить налоги в цену и пересчитать себестоимость»; в форме подтверждённого незаблокированного заказа доступна одноимённая кнопка. Окно показывает поле «Заказы на закупку»: кнопка «Пересчитать себестоимость» применяет исправление, «Отмена» закрывает окно без изменений. Возможность не добавляет и не удаляет поля в формах закупки, чека или счёта. Требуются права руководителя закупок и склада и доступ к затронутым источникам.
>
> Связанный черновой, проведённый или отменённый счёт покупателю сам по себе не запрещает пересчёт допустимого оплаченного или завершённого чека. Исправленная закупочная цена и подтверждённые складские движения определяют историческую себестоимость продажи и связанного возврата; маржа обновляется. Суммы, строки, оплаты, взаиморасчёты и состояния финансовых документов сохраняются. При наличии проводки себестоимости затронутого товара в связанном счёте или его сторно весь пересчёт отклоняется до хозяйственных изменений. Проводки только другого товара не мешают операции.
>
> Например, для продажи одной единицы и её возврата с подтверждённой новой исторической стоимостью 120 сохранённые стоимости становятся 120 и −120, даже если к чекам привязаны счета. Прямой завершённый складской источник допускается при открытой смене; общий источник требует закрытой смены и доказанного распределения. Повтор без новых налогов не меняет данные. Неоднозначный источник или защищённая финансовая стоимость вызывает отказ всего набора без частичных изменений.
^feature-card

## Purpose

Allow explicit purchase tax inclusion and historical cost recomputation to include otherwise eligible invoiced POS sales and refunds while preserving financial documents and rejecting concrete protected valuation dependencies.

## Requirements

### Requirement: Customer invoices do not independently prevent cost recomputation

The explicit purchase correction SHALL include otherwise eligible paid or completed POS sales and linked refunds regardless of whether a linked customer invoice is draft, posted or cancelled. Invoice presence or status alone MUST NOT cause refusal, omission or retention of an outdated POS cost. The existing periodic FIFO scope, complete historical evidence, stock-source attribution and signed order-date currency conversion SHALL remain mandatory. Direct completed sources SHALL remain eligible in open sessions; shared sources SHALL require a closed session and complete same-direction attribution. The same rules SHALL apply to eligible goods with inventory tracking disabled. This requirement supersedes only the blanket invoice prohibition in the base purchase correction; all other eligibility restrictions remain applicable.

#### Scenario: I01 Recompute an invoiced sale with a direct source
- **GIVEN** an otherwise eligible completed POS sale has a posted customer invoice and a completed direct stock source in an open session
- **WHEN** purchase correction changes its historical unit cost from 100 to 120
- **THEN** its one-unit saved cost becomes 120 and its margin reflects that cost
- **AND** the invoice does not prevent application and the session stays open

#### Scenario: I02 Accept a draft or cancelled invoice without protected cost entries
- **GIVEN** an otherwise eligible paid or completed sale has a linked draft or cancelled customer invoice without protected cost entries
- **WHEN** purchase correction is applied
- **THEN** the sale's cost is recomputed and the invoice keeps its original state

#### Scenario: I03 Recompute an invoiced sale and linked refund
- **GIVEN** an eligible one-unit sale and its linked one-unit refund have customer financial documents and proven completed movements within the affected interval
- **WHEN** purchase correction produces a historical unit cost of 120
- **THEN** the sale's cost becomes 120 and the refund's cost becomes -120 with corresponding margins

#### Scenario: I04 Include invoiced lines sharing a closed-session source
- **GIVEN** eligible invoiced and uninvoiced sales share a complete same-direction source in a closed session
- **WHEN** purchase correction is applied
- **THEN** all affected lines receive costs from that corrected source without omissions due to invoice presence

#### Scenario: I05 Use historical cost for invoiced goods without inventory tracking
- **GIVEN** eligible invoiced goods have inventory tracking disabled and a proven historical source distinct from today's product cost
- **WHEN** purchase correction is applied
- **THEN** the affected sale and linked refund use their signed corrected historical costs
- **AND** the inventory-tracking setting remains unchanged

### Requirement: Refuse concrete protected financial dependencies

Before any correction is applied, the operation SHALL reject existing cost-of-goods-sold entries for the affected products in related customer invoices or credit notes, including relevant reversal documents. Existing cost entries SHALL remain protected even if the current product configuration uses periodic valuation; a zero amount MUST NOT hide their existence. Entries belonging solely to unaffected products MUST NOT independently prevent correction. Existing supplier-bill, locked-period, stock-accounting, analytic and protected-valuation restrictions SHALL remain in effect. Refusal SHALL identify the affected accessible POS order and the concrete dependency category without exposing inaccessible financial details. No partial correction or compensating financial posting SHALL occur.

#### Scenario: I06 Reject historical financial cost entries
- **GIVEN** an otherwise eligible affected sale or refund has a related customer financial document or reversal containing cost-of-goods-sold entries for an affected product
- **WHEN** purchase correction is requested
- **THEN** the entire selection is rejected with that cost dependency identified
- **AND** current periodic valuation, document status or a zero entry amount does not bypass protection

#### Scenario: I07 Ignore financial cost entries for an unaffected product
- **GIVEN** a shared customer invoice contains cost-of-goods-sold entries solely for products outside the correction scope
- **WHEN** an otherwise eligible correction is applied
- **THEN** those unrelated entries do not prevent correction and remain unchanged

#### Scenario: I08 Retain existing financial and valuation restrictions
- **GIVEN** a selected purchase has a non-cancelled supplier bill, or required revaluation overlaps a locked period, stock or analytic posting, or protected valuation
- **WHEN** correction involving an invoiced POS sale is requested
- **THEN** the existing specific refusal and full rollback remain effective

#### Scenario: I09 Retain stock-source eligibility restrictions
- **GIVEN** an invoiced sale has an unfinished or ambiguous source, an open shared-session source or another unsupported POS structure
- **WHEN** purchase correction is requested
- **THEN** the whole correction is refused for that source condition without substituting today's product cost

### Requirement: Preserve financial and commercial facts

Successful correction SHALL update only the already authorized purchase terms, historical stock values, current product cost and affected POS costs and margins. Customer invoices, credit notes, journal items, reconciliation links, payment amounts, residual balances and financial-document states MUST remain unchanged. POS quantities, sale prices, discounts, customer taxes, totals, states and session facts SHALL remain unchanged. No invoice reset, cancellation, reposting, new invoice or financial adjustment SHALL be performed.

#### Scenario: I10 Preserve an invoiced sale's financial evidence
- **GIVEN** an eligible posted customer invoice is partially or fully reconciled with payments
- **WHEN** purchase correction updates the associated POS costs
- **THEN** invoice content, journal entries, reconciliation, payment and residual amounts, document states and commercial sale facts equal their values before correction

### Requirement: Preserve atomicity, permissions and explicit lifecycle

The extension SHALL use the existing explicit action, authorization, company isolation, transaction boundary and source-consistency protections. Hidden financial cost dependencies MUST NOT be treated as absent; existence checks MAY refuse the operation without disclosing their content and MUST NOT require new accounting write permissions. Concurrent linking, creation or modification of a relevant customer financial dependency SHALL be serialized with correction or cause a clean retry from current facts. Opening or cancelling the dialog, ordinary processing, copying, importing and module upgrades MUST NOT trigger this historical correction. A successful repeat without newly convertible taxes SHALL remain a no-op.

#### Scenario: I11 Cancel the existing dialog
- **WHEN** the user opens and cancels correction for purchases related to invoiced sales
- **THEN** no purchase, stock, POS or financial business data changes

#### Scenario: I12 Roll back a late failure and retry
- **GIVEN** a correction involving invoiced sales has updated purchase and stock values within its transaction
- **WHEN** a required POS update fails
- **THEN** the entire attempt is rolled back
- **AND** a later retry starts from the unchanged business facts

#### Scenario: I13 Repeat a successful correction
- **GIVEN** the selected purchases have already been corrected and contain no newly convertible taxes
- **WHEN** the user applies correction again
- **THEN** no price, stock value, POS cost or financial fact is changed

#### Scenario: I14 Detect a concurrent customer financial dependency
- **GIVEN** a related invoice, reversal or affected product cost entry is linked, created or changed concurrently with correction
- **WHEN** correction reaches application
- **THEN** it uses a consistent serialized set of facts or fails for retry without partial business changes
- **AND** an older snapshot cannot overlook the protected dependency

#### Scenario: I15 Preserve access and company boundaries
- **WHEN** correction is invoked by an unauthorized caller or across unauthorized companies
- **THEN** existing access restrictions reject the operation

#### Scenario: I16 Preserve ordinary processing outside correction
- **WHEN** users sell, return, invoice, close sessions, copy or import documents, or upgrade the module without invoking purchase correction
- **THEN** their ordinary business behavior remains unchanged and no historical correction occurs

#### Scenario: I17 Detect a hidden financial dependency
- **GIVEN** an authorized correction caller cannot read a related financial document containing protected cost entries
- **WHEN** purchase correction is requested
- **THEN** the complete correction is refused without exposing private financial amounts
- **AND** the hidden dependency is not treated as absent
