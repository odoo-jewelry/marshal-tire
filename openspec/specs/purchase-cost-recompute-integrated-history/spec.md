# Integrated Purchase Cost Recompute for Consolidated and Historical Stock Histories Specification

> [!abstract] Пересчёт закупочной себестоимости объединённых товаров и исторических списаний
> Позволяет включить налоги в закупочную цену и пересчитать подтверждённую себестоимость полностью объединённых товаров и связанных исторических списаний.
>
> **Использование:**
>
> В приложении «Закупки» выберите заказы в списке и действие «Включить налоги в цену и пересчитать себестоимость» либо одноимённую кнопку в форме подтверждённого незаблокированного заказа. В окне поле «Заказы на закупку» показывает выбранные документы; кнопка «Пересчитать себестоимость» применяет исправление, «Отмена» закрывает окно без изменений. Возможность не добавляет и не удаляет поля в формах закупки, товара, исторического списания или чека. Требуются права руководителя закупок и склада, доступ ко всем затронутым источникам, а для изменения стоимости исторического списания — специальное разрешение на исторические складские операции.
>
> После полного подтверждённого объединения карточек основная карточка может участвовать в пересчёте вместе с обычными товарами. Исправляются закупочная цена, стоимость поступлений, последующих исторических и обычных расходов, возвратов, себестоимость и маржа затронутых чеков. Историческое списание меняет только стоимость; его исходный чек, снимки истории, количества, складские движения и финансовые факты сохраняются. Например, два поступления по разным ценам до исторического списания участвуют в расчёте по времени поступления, а более позднее невыбранное поступление сохраняет свою стоимость.
>
> Неполное объединение, поглощённая карточка, незавершённое движение, защищённая стоимость или финансовая зависимость вызывают отказ всего выбранного набора до изменений. Результат показывает фактически обработанные строки и движения, включая исторические расходы. Повтор без новых налогов не меняет стоимость повторно; обычные закупки и продажи продолжают работать как прежде. Отдельный журнал исправлений не создаётся.
^feature-card

## Purpose

Extend explicit purchase tax inclusion and historical cost recomputation to proven fully consolidated product histories and eligible historical stock write-offs, without changing physical facts or creating a separate correction journal.

## Requirements

### Requirement: Proven complete consolidation is eligible

The explicit purchase correction SHALL accept a canonical product whose entire absorbed history has been consolidated into that product in the selected company. Every absorbed card MUST be covered by completed full-history consolidation evidence and MUST have neither non-cancelled stock movements nor nonzero stock quantities remaining, including outside the selected company. Multiple genuine receipts at different costs MUST NOT by themselves prevent correction. Absorbed cards, stock-only consolidation, incomplete evidence and active synthetic consolidation movements SHALL remain unsupported. The caller MUST NOT need to repeat an already completed consolidation. This eligibility rule SHALL apply equally to otherwise eligible goods with inventory tracking enabled or disabled.

#### Scenario: H01 Correct a fully consolidated canonical product
- **GIVEN** two eligible taxed purchases now belong to one canonical product with proven complete consolidation and real receipts at different costs
- **WHEN** the purchase correction is applied
- **THEN** both purchases and their affected cost history are corrected using the canonical product's complete chronological history
- **AND** no new consolidation is required or performed

#### Scenario: H02 Refuse incomplete consolidation evidence
- **GIVEN** a canonical product has only stock-balance consolidation, an uncovered absorbed card, active synthetic consolidation movements, or remaining non-cancelled movements or nonzero quantities on an absorbed card
- **WHEN** correction is requested
- **THEN** the entire selection is refused with the incomplete consolidation condition identified, without changing values

#### Scenario: H03 Refuse an absorbed card as the correction target
- **GIVEN** a selected purchase still references an absorbed product card
- **WHEN** correction is requested
- **THEN** the request is refused with the absorbed-card condition identified rather than independently valuing it or silently redirecting its purchase line

#### Scenario: H04 Preserve the original consolidation evidence
- **GIVEN** consolidation records retain prices and values from before the consolidation
- **WHEN** an eligible purchase correction changes current prices and costs
- **THEN** the consolidation records, their original snapshots and their product relationships remain unchanged
- **AND** the earlier snapshot amounts are not substituted for current receipt values

### Requirement: Historical write-offs participate through valuation only

A completed historical stock write-off SHALL participate in the same chronological FIFO recomputation as other eligible outgoing movements when its history, physical dimensions and sources satisfy the existing purchase correction rules. Its historical origin alone MUST NOT cause refusal. Only its valuation MAY change. Its source POS document SHALL remain a preparation source and MUST NOT become an ordinary sale or receive recalculated POS costs. The completed stock movements SHALL determine quantities; legitimate edits to the write-off's lines before completion MUST NOT be rejected merely because their products or quantities differ from the preparation source. Existing historical-source snapshots SHALL remain historical evidence; a legitimate earlier full consolidation MUST NOT require rewriting those snapshots to current product identities. Unselected later receipts SHALL retain their own values, and earlier issues MUST NOT use later receipt costs or current product-card costs. Ordinary eligible sales and refunds SHALL continue to receive costs from their actual stock sources.

#### Scenario: H05 Revalue a historical write-off from corrected receipts
- **GIVEN** eligible receipts contain 20 units at 8.93 and 100 units at 9.00, both with excluded 20 percent tax, followed by a historical write-off of 31 units before any other issue, whose preparation quantity was legitimately edited from the source POS quantity before completion
- **WHEN** both purchases are corrected
- **THEN** the rounded receipt unit prices become 10.72 and 10.80, the receipt values become 214.40 and 1080.00, and the historical write-off value becomes 333.20

#### Scenario: H06 Preserve the historical preparation source
- **GIVEN** a completed historical write-off originates from a draft or cancelled POS document and an earlier full consolidation legitimately changed its product references
- **WHEN** the eligible purchase correction is applied
- **THEN** the source document retains its current state, lines, amounts, saved costs and payment facts
- **AND** the historical source snapshot remains unchanged and does not become a live valuation source

#### Scenario: H07 Respect the time of an unselected later receipt
- **GIVEN** a corrected receipt is followed by a historical write-off and an unselected later receipt at a different cost
- **WHEN** the correction is applied
- **THEN** the historical write-off uses only eligible preceding valuation evidence
- **AND** the later receipt retains its recorded value and contributes normally to subsequent FIFO consumption

#### Scenario: H08 Recompute ordinary POS costs after a historical write-off
- **GIVEN** an eligible canonical product has a historical write-off followed by ordinary paid or completed sales with proven stock sources, including a paid direct-source sale in an open session
- **WHEN** the correction is applied
- **THEN** every affected ordinary POS line receives its corrected historical source cost and corresponding margin
- **AND** the open session remains open and the historical preparation source is excluded from those POS updates

### Requirement: Existing valuation protection and authorization remain enforceable

The extension SHALL retain purchase-manager and stock-manager permissions, normal record access, company isolation and all existing financial and valuation protections. Changing a historical write-off value SHALL additionally require the existing permission for historical stock operations. A previous protected cost correction, manual stock valuation, relevant financial dependency or locked period SHALL still cause atomic refusal. Fully consolidated history MUST NOT bypass these conditions. Client-supplied flags, values or context MUST NOT authorize protected valuation, broaden the validated records or permit physical edits. Hidden source amounts MUST NOT be disclosed when access is insufficient.

#### Scenario: H09 Refuse protected valuation or financial history
- **GIVEN** otherwise eligible merged or historical history contains a protected previous cost correction, manual valuation, non-cancelled supplier bill including a draft bill, stock-related accounting or analytic entry, landed-cost adjustment, or locked valuation period
- **WHEN** correction is requested
- **THEN** the existing explained refusal applies to the entire selection without rewriting or removing the protected evidence

#### Scenario: H10 Require historical operation permission and source access
- **GIVEN** a caller has purchase and stock manager permissions but lacks historical operation permission or required source access
- **WHEN** the correction would change a historical write-off
- **THEN** the request is denied without partial changes or disclosure of hidden amounts

#### Scenario: H11 Isolate company valuation
- **GIVEN** the caller can access two companies and an affected shared product has unrelated receipts in the other company
- **WHEN** an eligible merged or historical correction runs in one company
- **THEN** only the selected company's receipts contribute costs and only that company's values are updated
- **AND** the other company's quantities and valuation remain unchanged

#### Scenario: H12 Reject client attempts to bypass historical protection
- **WHEN** a caller supplies forged context or valuation values through a direct request or ordinary write to a completed historical movement
- **THEN** the caller cannot choose the corrected cost, authorize an unrelated movement or change protected physical dimensions
- **AND** the explicit action can update only values calculated from its validated history

### Requirement: Consistent atomic recomputation across all sources

The operation SHALL validate the complete selected batch and apply purchase, receipt, historical issue, ordinary issue, return, POS and product-cost updates atomically. Concurrent changes to canonical or absorbed cards, consolidation membership, source documents or valuation history MUST NOT result in an incomplete or stale computation. New source records invisible to an earlier read MUST be detected. A conflicting attempt SHALL use a consistent current history or fail for retry without partial values. Existing retry behavior SHALL remain unchanged.

#### Scenario: H13 Roll back a failure after historical valuation
- **GIVEN** an attempt has changed purchase, receipt and historical write-off values
- **WHEN** a later required POS or product-cost update fails
- **THEN** the complete attempt is rolled back, including the historical value, and a retry starts from unchanged facts

#### Scenario: H14 Detect concurrent consolidation changes
- **GIVEN** another transaction changes consolidation membership or adds a movement or nonzero quantity to an absorbed card during correction
- **WHEN** the operation would otherwise rely on the earlier consolidation proof
- **THEN** it uses consistent current evidence or refuses the attempt for retry without partial changes

#### Scenario: H15 Detect concurrent historical source changes
- **GIVEN** a historical source document changes or another transaction adds relevant stock or POS history during correction
- **WHEN** the operation would otherwise compute costs from incomplete or stale sources
- **THEN** it uses consistent current evidence or refuses the attempt for retry without partial changes

### Requirement: Preserve physical facts and the explicit action lifecycle

Correction SHALL retain quantities, movement identities, product identities, dates, states, locations, links to source documents, payments, revenue and accounting facts. It MUST NOT cancel and recreate or physically repost stock documents. It MUST NOT create a separate persistent journal, reviewed cost operation, correction flag or mandatory reason. The existing dialog, cancellation and tax-free repeat behavior SHALL remain. Two-decimal HALF-UP rounding, unchanged discounts and removal of converted taxes SHALL continue to apply. Ordinary operations, copying, imports and module installation or upgrade MUST NOT run the explicit historical correction or weaken existing historical-document protections. Optional history capabilities being absent MUST NOT prevent otherwise supported ordinary purchase correction.

#### Scenario: H16 Preserve the physical and financial facts
- **WHEN** an eligible merged and historical correction completes
- **THEN** stock quantities, movement identities and dimensions, document states and relationships, payments, revenue and accounting facts match their pre-correction values

#### Scenario: H17 Complete without a separate correction journal
- **WHEN** the eligible correction completes
- **THEN** its updated values and actual processed-record summary are available without a new persistent correction record, review stage, reason or marker

#### Scenario: H18 Cancel the correction dialog
- **WHEN** a user opens and cancels the existing dialog for eligible merged or historical purchases
- **THEN** no purchase, stock or POS business values change

#### Scenario: H19 Repeat a successful correction
- **GIVEN** the selected purchases have already been corrected and contain no new positive taxes
- **WHEN** the action is repeated
- **THEN** it reports no further corrections and does not add tax amounts again or cause valuation drift

#### Scenario: H20 Preserve ordinary operations outside the action
- **WHEN** ordinary purchasing, stock processing, POS processing, copying, import or an existing cost tool runs without the explicit purchase correction
- **THEN** its existing behavior, permissions and historical-document protections remain unchanged

#### Scenario: H21 Upgrade safely and retain optional-module compatibility
- **WHEN** the capability is installed or upgraded, including on a database without optional consolidation or historical-write-off functionality
- **THEN** no business prices or costs are corrected automatically and ordinary eligible purchase correction remains available

#### Scenario: H22 Retain mixed goods and supported return behavior
- **GIVEN** an eligible mixed batch contains goods with inventory tracking enabled and disabled, completed historical write-offs, and supported ordinary linked customer returns or proven historical shortages
- **WHEN** the correction is applied
- **THEN** all affected values follow the existing receipt, FIFO, shortage, return and POS rules without changing tracking settings, discounts or quantities
- **AND** converted prices use two-decimal HALF-UP rounding and their converted taxes are removed

### Requirement: Validate the complete purchase selection

The correction SHALL handle a complete otherwise eligible selection containing both merged and unmerged products and historical write-offs without silently omitting products, movements or affected POS costs. Every affected historical expense SHALL be included in the existing outgoing-movement result count. An unsupported dependency anywhere in the selected batch SHALL produce a specific atomic refusal rather than a partial successful result.

#### Scenario: H23 Correct the complete initial purchase batch
- **GIVEN** the acceptance copy contains eligible purchases P00001 through P00005, four proven fully consolidated canonical products and 22 affected historical expenses from WH/POS/00071
- **WHEN** the entire selection is corrected in one request
- **THEN** all selected taxed lines and every required downstream cost are corrected without skipping historical expenses or ordinary affected POS lines
- **AND** the reported counts match the actual changed scope and stock balances reconcile after correction
