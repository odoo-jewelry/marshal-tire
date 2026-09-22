# Purchase Cost Recompute for Inventory Adjustments Specification

> [!abstract] Пересчёт закупочной себестоимости с учётом корректировок запасов
> Позволяет при явном исправлении закупки пересчитать историческую стоимость обычных излишков, недостач и списаний вместе с последующими расходами.
>
> **Использование:**
>
> В приложении «Закупки» выберите заказы в списке и действие «Включить налоги в цену и пересчитать себестоимость» либо одноимённую кнопку в форме подтверждённого незаблокированного заказа. В окне поле «Заказы на закупку» показывает выбор; кнопка «Пересчитать себестоимость» применяет исправление, «Отмена» закрывает окно без хозяйственных изменений. Возможность не добавляет, не меняет и не удаляет поля в формах закупки, корректировки запасов, списания или чека. Нужны права руководителя закупок и склада и доступ ко всем затронутым документам.
>
> Обычная недостача и штатное списание участвуют в исторической очереди расходов. Обычный излишек получает стоимость из подтверждённого остатка непосредственно перед ним; если остаток неположителен, используется цена последнего доказанного более раннего поступления. Например, пять оставшихся единиц по 120 и пять по 200 дают излишку из двух единиц стоимость 320. Последующие продажи и возвраты получают пересчитанную себестоимость; количество списаний не включается в продажи. Сообщение результата отдельно показывает излишки, недостачи и списания.
>
> Неподтверждённое происхождение корректировки, защищённая оценка, финансовые зависимости, закрытый период или неоднозначный порядок движений вызывают отказ всего набора без частичных изменений. Количества, даты, документы, выручка и проводки сохраняются. Повтор исправленной закупки без новых налогов ничего не меняет; обычные складские и кассовые операции продолжают работать как прежде.
^feature-card

## Purpose

Extend explicit purchase tax inclusion and historical FIFO cost correction to ordinary inventory gains, inventory losses and scrapping, preserving physical facts and protected valuation evidence.

## Requirements

### Requirement: Ordinary inventory losses and scrapping participate in historical FIFO

The explicit purchase correction SHALL accept completed ordinary inventory losses and scrapping from the supported internal stock location to an inventory-loss location, in addition to existing supported customer issues. These losses SHALL consume the same historical FIFO sequence as other expenses. Affected losses from the earliest corrected receipt through application time SHALL be revalued. Their source document type SHALL be validated; an inventory-loss destination alone MUST NOT authorize arbitrary transfers or synthetic product-consolidation movements. Existing product, company, ownership, unit, tracking, quantity-reconciliation and valuation restrictions SHALL remain.

#### Scenario: I01 Revalue an inventory loss across receipt costs
- **GIVEN** two available units have corrected unit cost 120 and three later units retain an unselected purchase cost of 200
- **WHEN** a subsequent inventory loss of three units is recomputed
- **THEN** the loss value is 440 and the two remaining units are valued at 400

#### Scenario: I02 Revalue an ordinary scrap document
- **GIVEN** one unit was purchased at 725 with excluded 20 percent tax and subsequently scrapped through an inventory-loss location
- **WHEN** that purchase is corrected
- **THEN** the receipt and scrap expense are each valued at 870 and the stock quantity remains zero

#### Scenario: I03 Reject an unproven adjustment source
- **GIVEN** an inventory-loss transfer has neither a supported inventory-count origin nor a valid completed scrap origin
- **WHEN** purchase correction is requested
- **THEN** the entire selection is refused with the unsupported source identified

### Requirement: Inventory gains use reconstructed historical cost

Every ordinary inventory gain inside the correction interval SHALL be revalued using the corrected historical evidence immediately before the gain. For a positive pre-gain quantity, its unit cost SHALL equal the FIFO value of that whole remaining quantity divided by that quantity. The gain SHALL enter subsequent FIFO at its own date and its corrected value. Neither today's product cost nor future receipts SHALL supply this value. Unselected purchase receipts SHALL retain their recorded costs. Inventory gain values MUST NOT be obtained by applying a uniform tax multiplier or by rounding their derived unit costs using purchase-price rounding rules.

If the pre-gain quantity is zero or negative, the unit cost SHALL be the value per unit of the last proven eligible incoming movement strictly earlier than the gain, using that movement's corrected value when applicable. This is an explicit historical correction policy and MUST NOT be represented as recovery of an unknown historical product-card cost. A missing, nonpositive or nonfinite valuation basis SHALL cause an explained atomic refusal. Existing unsupported incoming-value restrictions SHALL remain.

#### Scenario: I04 Value a gain from all remaining FIFO receipts
- **GIVEN** five remaining units have corrected unit cost 120 and five remaining units have unselected unit cost 200
- **WHEN** an inventory gain of two units is recomputed
- **THEN** the gain is valued at 320, using unit cost 160
- **AND** the total quantity of twelve units is valued at 1920

#### Scenario: I05 Exclude future receipts and current product cost
- **GIVEN** the corrected pre-gain remainder has unit cost 63.65, a later purchase costs 900 and today's product cost differs again
- **WHEN** a one-unit historical gain is recomputed
- **THEN** its value is 63.65, independent of the later receipt and current product cost
- **AND** the later unselected receipt retains its recorded value

#### Scenario: I06 Propagate a gain through subsequent losses and gains
- **GIVEN** two units at corrected cost 120 are followed by a one-unit gain, a two-unit loss and a later one-unit gain
- **WHEN** purchase history is recomputed
- **THEN** the first gain is 120, the loss is 240, the second gain is 120 and the remaining two units are valued at 240

#### Scenario: I07 Value a gain after stock reaches zero
- **GIVEN** stock is zero and its last proven earlier receipt has corrected unit cost 120
- **WHEN** a two-unit inventory gain is recomputed
- **THEN** the gain is valued at 240 using that earlier receipt

#### Scenario: I08 Value a gain while stock is negative
- **GIVEN** stock is negative three units and its last proven earlier receipt has corrected unit cost 120
- **WHEN** an inventory gain of five units is recomputed
- **THEN** the gain is valued at 600 and the remaining two units are valued at 240
- **AND** no missing physical receipts are invented

#### Scenario: I09 Refuse an unprovable gain cost
- **GIVEN** a gain has no positive provable historical valuation basis, although a future purchase or current product cost exists
- **WHEN** correction is requested
- **THEN** the entire selection is refused without preserving a partial purchase correction or substituting today's cost

### Requirement: Chronology and correction boundaries remain explicit

Earlier inventory gains, losses and scrapping SHALL remain unchanged and contribute their recorded evidence to the affected history. An incoming and outgoing movement at the same timestamp for one product SHALL remain unsupported. A gain sharing a timestamp with a different incoming source type SHALL also cause refusal because the pre-gain cost ordering is not proven. Multiple ordinary gains alone at one timestamp SHALL use the same strictly earlier cost basis; their own values SHALL NOT contribute to that basis. Existing same-timestamp outgoing ordering SHALL be preserved and include eligible losses and scrapping.

#### Scenario: I10 Preserve adjustments before the corrected receipt
- **GIVEN** an inventory gain, loss or scrap expense predates the earliest corrected receipt for its product
- **WHEN** a later purchase is corrected
- **THEN** that earlier adjustment retains its value and serves only as historical evidence

#### Scenario: I11 Preserve refusal for mixed movement directions
- **GIVEN** an inventory gain and an inventory loss share one timestamp for the same product
- **WHEN** correction is requested
- **THEN** the complete selection is rejected as chronologically ambiguous

#### Scenario: I12 Refuse a gain simultaneous with another incoming source
- **GIVEN** a gain and a purchase receipt or customer return share one timestamp for the same product
- **WHEN** correction is requested
- **THEN** the entire selection is rejected without choosing an arbitrary cost order

#### Scenario: I13 Handle multiple simultaneous gains without self-reference
- **GIVEN** the strictly earlier remainder is five units at corrected unit cost 120 and two ordinary gains of one unit each share the next timestamp
- **WHEN** history is recomputed
- **THEN** each gain is valued at 120 and the remaining seven units are valued at 840

### Requirement: POS costs reflect real sales after inventory corrections

Revalued gains, losses and scrapping SHALL affect subsequent supported sales through their FIFO evidence. Customer returns SHALL retain the existing proportional original-issue rule and participate in subsequent FIFO. Inventory losses and scrapping MUST NOT be allocated as sold quantities or directly added to POS cost. Linking a scrap document to a POS-related delivery MUST NOT make it a sale source. Existing historical preparation documents and their stored costs SHALL remain protected from ordinary POS updates.

#### Scenario: I14 Propagate corrected gain cost to a sale and return
- **GIVEN** an eligible purchase is exhausted, a later gain obtains corrected unit cost 120, and an ordinary POS sale of that unit has a linked return
- **WHEN** the purchase is corrected
- **THEN** the gain, sale expense and stock return are each valued at 120
- **AND** the POS sale cost is 120 and its refund cost is -120

#### Scenario: I15 Separate scrapping linked to a POS delivery
- **GIVEN** a POS-related delivery includes one sold unit and a distinct supported scrap movement for another unit
- **WHEN** its purchase history is corrected to unit cost 120
- **THEN** the sale expense and scrap expense are each valued at 120
- **AND** the POS sale receives cost 120 for its one sold unit, without including the scrap quantity or expense

### Requirement: Existing valuation protections cover adjustments

Every adjustment whose value would change SHALL undergo the existing access, financial, period, manual-valuation and protected-history checks before any correction is applied. Synthetic consolidation movements and incomplete or absorbed product histories SHALL remain unsupported. No adjustment origin SHALL bypass these protections. The operation SHALL remain isolated to its one authorized company, including the historical cost fallback at zero or negative stock.

#### Scenario: I16 Refuse protected adjustment valuation
- **GIVEN** an affected gain, loss or scrap expense has a manual valuation, stock accounting or analytic entry, landed-cost adjustment, protected cost correction, or locked valuation date
- **WHEN** correction is requested
- **THEN** the whole selection is refused without rewriting or removing the protected evidence

#### Scenario: I17 Preserve consolidation restrictions
- **GIVEN** selected history includes an active synthetic transfer between merged cards or lacks proven full-history consolidation
- **WHEN** correction is requested
- **THEN** the complete selection is refused even when that transfer uses an inventory-loss location or has an inventory-count flag

#### Scenario: I18 Enforce adjustment access through every entry point
- **GIVEN** a caller lacks required read access to an adjustment source or write access to a gain, loss or scrap movement that would change
- **WHEN** correction is requested through the interface or directly
- **THEN** the request is denied without updates or disclosure of hidden amounts

#### Scenario: I19 Isolate historical gain cost by company
- **GIVEN** a shared product has a later or more expensive receipt in another company
- **WHEN** a gain is corrected in the authorized company, including at zero or negative stock
- **THEN** only that company's eligible earlier incoming values contribute to the gain cost
- **AND** the other company's quantities and values remain unchanged

### Requirement: Atomic lifecycle and physical facts are preserved

Purchase prices, receipt values, adjustment values, other affected expenses, returns, POS costs and product costs SHALL change atomically. Concurrent stock counts, scrapping, source changes and overlapping corrections MUST NOT produce stale or mixed results. Existing serialization and retry behavior SHALL apply. Physical quantities, dates, identities, states, locations, source links, payments, revenue and accounting entries SHALL remain unchanged. Opening or cancelling the action SHALL NOT change business values. Repeating successful tax-free purchases SHALL remain a no-op; this extension does not introduce a standalone revaluation action.

#### Scenario: I20 Roll back a failure after gain valuation
- **GIVEN** purchase, receipt and gain values have changed within an attempted correction
- **WHEN** a subsequent required expense, POS or product-cost update fails
- **THEN** every change from the attempt is rolled back

#### Scenario: I21 Detect concurrent adjustment changes
- **WHEN** another transaction adds or changes a relevant inventory count, scrap movement or valuation source during correction
- **THEN** correction uses one consistent history or fails for retry without partially mixed values

#### Scenario: I22 Preserve physical adjustment documents
- **WHEN** an eligible selection containing gains, losses and scrapping is corrected
- **THEN** its quantities, movement and source-document identities, dates, states, locations, links, payments, revenue and accounting entries match the original facts

#### Scenario: I23 Repeat a successful correction
- **GIVEN** the selected purchases were corrected successfully and have no new positive taxes
- **WHEN** the action is repeated
- **THEN** no purchase or valuation values change and the result reports no correction

#### Scenario: I24 Cancel before applying
- **WHEN** the user opens and cancels the action for purchases with inventory adjustments
- **THEN** all business values remain unchanged

### Requirement: Results and deployment remain compatible

The existing result SHALL report actual revalued gain, inventory-loss and scrap-movement counts separately. Existing outgoing totals SHALL include losses and scrap expenses, while purchase receipt counts SHALL remain purchase receipt counts. No separate permanent correction journal, new mandatory workflow or automatic historical revaluation on deployment SHALL be introduced. Ordinary operations outside the explicit action SHALL retain their standard behavior.

#### Scenario: I25 Upgrade without changing historical values
- **WHEN** the extension is installed or upgraded on existing purchases and adjustments
- **THEN** no purchase price, adjustment value or POS cost is automatically changed

#### Scenario: I26 Preserve ordinary processing
- **WHEN** users perform purchasing, inventory counts, scrapping, sales, copying, imports or existing cost actions without the explicit purchase correction
- **THEN** their existing behavior, permissions and protections remain unchanged

#### Scenario: I27 Report adjustment counts without double counting
- **GIVEN** a successful correction revalues one purchase receipt, two ordinary gains, three inventory losses and four scrap movements without other expenses
- **WHEN** its result is displayed
- **THEN** it reports one purchase receipt, two gains, three inventory losses, four scrap movements and seven total outgoing movements
- **AND** no separate permanent correction journal is created
