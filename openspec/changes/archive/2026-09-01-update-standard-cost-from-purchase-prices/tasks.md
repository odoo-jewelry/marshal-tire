## 1. Базовое состояние и valuation-значения строки

- [x] 1.1 Перед implementation подтвердить, что `revise-purchase-price-control-actions` реализован и проверен; если changes объединяются, сначала согласованно перенести его Fill/Update/snapshot foundation без возврата confirm-driven сохранения.
- [x] 1.2 Добавить `purchase_stock` как явную зависимость addon и обновить версию модуля, сохранив существующий data order.
- [x] 1.3 Добавить на `purchase.order.line` non-stored `valuation_purchase_price`, переиспользующий стандартный `_get_stock_move_price_unit()` с датой заказа, и technical effective cost method без дублирования tax/UoM/currency логики.
- [x] 1.4 Добавить stored `copy=False` снимок `current_standard_price`, включить его в Fill и final refresh через `with_company(order.company_id)`, не выполняя product/lot/valuation writes.
- [x] 1.5 Расширить precision-aware discrepancy: cost-only расхождение участвует в `price_update_required` и order aggregate только при текущем Standard Price; AVCO/FIFO игнорируют cost pair.

## 2. Явное обновление стандартной себестоимости

- [x] 2.1 Расширить line Update: сформировать payload server-side и записывать `valuation_purchase_price` в company-specific `standard_price` только при текущем `cost_method == "standard"`, одной обычной ORM-записью вместе с reference/sales targets, без custom `sudo()`, SQL, commits или `disable_auto_revaluation`.
- [x] 2.2 После line Update синхронизировать standard-cost snapshots связанных строк из final product values и обеспечить no-op retry без дополнительного `product.value`.
- [x] 2.3 Расширить frozen payload Update All и определить последний standard-cost candidate для каждого `(company, product)`, чтобы last-line-wins записывал только одну итоговую `standard_price`/cost-history запись на продукт.
- [x] 2.4 Сохранить общую атомарность bulk product writes, стандартных `product.value`/lot side effects и snapshot refresh; AVCO/FIFO не должны получать custom cost payload ни в line, ни в bulk action.

## 3. Интерфейс и переводы

- [x] 3.1 Узко расширить embedded purchase-order lines: показать current и calculated standard cost только для Standard Price products и сохранить существующую all-state доступность Fill/Update actions.
- [x] 3.2 Обновить POT и русско-/украиноязычные переводы labels/help так, чтобы tax-included reference purchase price и valuation-compatible standard cost были однозначно различимы.

## 4. Автоматизированная проверка расчётов и снимков

- [x] 4.1 Добавить focused tests valuation cost для recoverable и cost-bearing taxes, discount, purchase UoM, foreign currency и exchange rate на дату заказа; отдельно подтвердить отличие от tax-included reference price.
- [x] 4.2 Проверить Fill/refill, стабильность и `copy=False` standard-cost snapshot, uninitialized существующие строки, company context и cost-only action visibility с currency precision.

## 5. Автоматизированная проверка действий и учёта

- [x] 5.1 Проверить line Update Standard и no-op retry во всех поддерживаемых состояниях PO, company-specific `standard_price`, штатную `product.value` history и стандартную propagation для lot-valuated Standard product.
- [x] 5.2 Проверить AVCO и FIFO, включая lot valuation и смену cost method между Fill/Update: Price Control меняет только reference/sales prices и не пишет product/lot cost.
- [x] 5.3 Проверить Update All для смешанного набора, нескольких Standard products и повторяющихся строк одного продукта: frozen values, last-line-wins, одна final cost-history запись и честный final snapshot discrepancy.
- [x] 5.4 Проверить права пользователя и atomic rollback line/bulk action, включая отсутствие частичных reference/sales/standard prices, `product.value`, lot costs и snapshots после ошибки.
- [x] 5.5 Сохранить regression coverage отсутствия standard-cost side effects у confirm, double approval, receipt, cancel, reset/reconfirm, lock/unlock, direct create/write/import и duplicate; API/RPC actions должны использовать те же server checks.

## 6. Upgrade и итоговая валидация

- [x] 6.1 Выполнить Python syntax/import, manifest dependency/version, XML/external-ID/view inheritance и translation checks без изменения standard Odoo sources.
- [x] 6.2 Прочитать фактический `/etc/odoo/odoo.conf`, обновить `purchase_price_control` на явной development DB через временный Odoo HTTP port начиная с `8077` и запустить focused backend suite.
- [x] 6.3 Проверить upgrade: создание `current_standard_price`, отсутствие backfill, `price_snapshot_initialized=False` у существующих строк и отсутствие изменений product/lot costs во время module update.
- [x] 6.4 Выполнить ручной non-browser smoke новых колонок и object-buttons в draft, confirmed, locked и cancelled PO; browser automation не создавать и не запускать.
