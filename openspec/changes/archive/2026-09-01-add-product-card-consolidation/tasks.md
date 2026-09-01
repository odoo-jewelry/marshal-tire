## 1. Addon, ownership и security boundary

- [x] 1.1 Создать `main/product_card_consolidation` с минимальными зависимостями `purchase_import` и `sale_management`, корректным manifest/data order и model/wizard/test initialization.
- [x] 1.2 Добавить product-management privilege и группу `product_card_consolidation.group_product_consolidation_manager`, ACL для persistent/transient models и server-side group guard для preview/confirm/API paths.
- [x] 1.3 Зафиксировать controlled administrative-write boundary: exact company должна входить в `allowed_company_ids`, разрешены только явные draft/configuration handlers, preserved history и произвольные ссылки не должны изменяться через `sudo()`.

## 2. Canonical metadata и identifier aliases

- [x] 2.1 Расширить product template canonical link/source relations с `copy=False`, index, self/cycle protection и запретом прямой записи вне consolidation service.
- [x] 2.2 Реализовать `product.identifier.alias` для `default_code`/`barcode` с normalization, company scope, source traceability и проверкой конфликтов с aliases и direct identifiers других active products.
- [x] 2.3 Добавить batch exact resolver и alias-aware backend product search, сохранив standard domain, access, active filtering, limit, direct-result semantics и ambiguity.
- [x] 2.4 Добавить server-side запрет unarchive ранее consolidated template/variant и разрешить последовательное поглощение новых eligible duplicates существующим canonical без alias loss.

## 3. Eligibility analyzer и preview data

- [x] 3.1 Реализовать единый read-only analyzer выбора ровно двух active templates и canonical/duplicate roles с учётом всех active/archived variants.
- [x] 3.2 Добавить batch blockers для exact company, product/storage type, UoM/category, tracking/lots, non-zero quantity/reservation и незавершённого inventory count.
- [x] 3.3 Сформировать расширяемую allowlist policy и preview categories для transferable configuration, editable drafts, preserved history, unknown references и canonical-wins scalar policy.
- [x] 3.4 Повторно выполнять полный analyzer непосредственно при confirm, чтобы stale preview или новое operational состояние не приводили к partial consolidation.

## 4. Configuration и draft reference handlers

- [x] 4.1 По фактическим Odoo 19 fields определить и реализовать natural keys для supplierinfo, pricelist rules, packaging, orderpoints, putaway rules и storage capacities; exact equivalents дедуплицировать, разные business values показывать как blockers.
- [x] 4.2 Объединить routes, taxes, tags и optional-product relations как set union без изменения canonical scalar/company-dependent values.
- [x] 4.3 Перевести через ORM только sale quotation lines в `draft`/`sent` и RFQ lines в `draft`/`sent`, сохраняя введённые quantity, UoM, description, price, taxes и discounts; остальные document states не менять.
- [x] 4.4 Перевести поддерживаемую durable project configuration, включая `purchase.import.profile.variant_template_id`, и оставить transient import state на standard cleanup lifecycle.
- [x] 4.5 Проверить handlers как batch recordsets и предоставить наследуемый registry/hook для явной поддержки ссылок будущих addon без generic FK update.

## 5. Atomic consolidation lifecycle

- [x] 5.1 Реализовать persistent business action: revalidate, выполнить controlled handlers, создать aliases, записать canonical link, архивировать duplicate через standard action и опубликовать один audit summary на canonical.
- [x] 5.2 Сохранить source chatter/attachments и все non-draft Sales/Purchase, Accounting, POS, Stock, return/scrap и generic references без изменения, обеспечив открытие archived source из истории.
- [x] 5.3 Не выполнять manual commit/rollback и не подавлять исключения; добавить тестовый extension hook для доказательства полного transaction rollback при ошибке между handlers и archive.
- [x] 5.4 Обеспечить безопасный retry после failed attempt и отказ от повторного использования уже archived/merged source после success.

## 6. Wizard и product views

- [x] 6.1 Реализовать transient wizard/preview lines, default selection из списка product templates, canonical selector, blocker/transfer/preserve summary и read-only preview без persistent writes.
- [x] 6.2 Добавить bound action в список product templates и отдельный final confirmation step с явным предупреждением об архивировании; cancellation на обоих шагах не должна вызывать business action.
- [x] 6.3 Расширить product form стабильными XPath: показать readonly canonical link на archived source и absorbed-source navigation на canonical только для разрешённой группы.

## 7. Purchase import integration

- [x] 7.1 Перевести `_build_lookup_cache` в `purchase_import` на общий batch resolver для direct/alias `default_code` и `barcode`, сохранив lookup priority и existing ambiguity errors.
- [x] 7.2 Обеспечить supplier-code resolution через перенесённый/deduplicated supplierinfo и подтвердить, что preview остаётся read-only, а unmatched create не планирует новый товар для former identifier.

## 8. Focused automated tests

- [x] 8.1 Покрыть wizard selection, cancellation, canonical preview policy и blockers: variants, company, type/UoM, tracking/lots, quant/reservation, inventory count и stale confirmation.
- [ ] 8.2 Покрыть configuration set union, natural-key exact dedup, conflicting-value blockers, draft quotation/RFQ transfer и неизменность confirmed/done/cancelled/posted/POS references.
- [x] 8.3 Покрыть archive/link, historical navigation, unarchive guard, repeated consolidation, audit summary и сохранение canonical scalar/company-dependent values.
- [x] 8.4 Покрыть alias normalization/uniqueness/company scope, direct-versus-alias ambiguity, backend lookup и `purchase_import` preview/apply по прежним code/barcode/supplier code.
- [x] 8.5 Покрыть dedicated-group UI/API access, cross-company denial, ограниченную область administrative writes, forced mid-operation rollback и успешный retry.
- [x] 8.6 Добавить regression tests обычного product search/archive/unarchive, стандартных Purchase/Sales/Stock flows и import без merge metadata.

## 9. Delivery validation

- [x] 9.1 Проверить Python syntax/imports, manifest dependencies/data order, XML/external IDs, `ir.model.access.csv`, group privilege и inherited view/action compilation.
- [x] 9.2 Установить/обновить `product_card_consolidation` в test DB на временном HTTP port согласно конфигурации Odoo и выполнить focused non-browser test suite.
- [ ] 9.3 Выполнить manual smoke wizard preview/confirmation, archived-source navigation, backend alias lookup и POS catalog refresh; явно отметить, что POS alias scanning и browser automation не проверялись и не входят в scope.
- [x] 9.4 Проверить upgrade safety на существующих products: установка не создаёт merge links/aliases, не меняет active flags и не требует data migration или cleanup.
