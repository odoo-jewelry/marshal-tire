## 1. Каркас addon и профили импорта

- [x] 1.1 Создать upgrade-safe addon `main/purchase_import` с корректным manifest, зависимостями и порядком загрузки security/views.
- [x] 1.2 Реализовать company-scoped `purchase.import.profile` и его mapping/lookup records с file options, 1-based header/data rows, exact lookup order, unmatched policy, creation mode и explicit product defaults.
- [x] 1.3 Добавить server-side constraints для уникального имени профиля в company, `data_row > header_row`, дублей lookup/target и согласованности creation mode/template/defaults.
- [x] 1.4 Добавить Purchase configuration action/menu и form/list views для профиля, mapping и lookup order без custom frontend.

## 2. Доступ и multi-company

- [x] 2.1 Добавить ACL: Purchase Users читают профили, Purchase Managers управляют ими; transient wizard records доступны запустившему пользователю.
- [x] 2.2 Добавить allowed-company record rule и `check_company`/domains для профиля, template, category, UoM, taxes и других company-sensitive ссылок.
- [x] 2.3 В apply-потоке явно проверять access к PO, `product.supplierinfo` и, когда нужно, `product.template`/`product.product`; не расширять ACL standard-моделей и не обходить их через import-level `sudo()`.

## 3. Wizard, parser и сопоставление

- [x] 3.1 Ограничить action пустым draft `purchase.order` и повторить lifecycle/empty-order guard в parse, preview и apply server methods.
- [x] 3.2 Реализовать локальный adapter: CSV через standard `base_import`, XLSX через runtime `openpyxl` с физическими 1-based header/data rows, выбором листа и лимитами размера/числа строк.
- [x] 3.3 Сформировать transient mapping из заголов файла, поддержать копирование из/сохранение в профиль и разрешать только фиксированные semantic targets.
- [x] 3.4 Реализовать normalization quantity/price/UoM/text/identifiers/attributes, required mappings и row-specific errors; отклонять invalid layout, empty data и incompatible UoM.
- [x] 3.5 Сохранить read-only preview с resolved/planned outcome и summary создаваемых строк без предупреждения об удалении; apply разрешать только при отсутствии ошибок и строк PO.
- [x] 3.6 Хранить digest файла/configuration и snapshot состава PO; сбрасывать valid preview при изменении wizard и отклонять stale apply.
- [x] 3.7 Для XLSX игнорировать unnamed physical columns merged-заголовка, завершать непрерывный data block на первой полностью пустой строке и сохранять исходные номера строк в preview/errors.
- [x] 3.8 Оставить на mapping/preview вторичную кнопку повторного чтения файла, перестраивающую mapping и сбрасывающую прежний preview.

## 4. Product resolution и creation

- [x] 4.1 Реализовать ordered batch exact lookup по commercial-vendor `product.supplierinfo.product_code`, `product.product.default_code` и `barcode`, с company filtering и ambiguity errors.
- [x] 4.2 Реализовать unmatched policy: reject либо standalone `product.template` с одним вариантом; для standalone creation требовать mapped product name и применять mapped values, затем profile defaults, затем ORM defaults.
- [x] 4.3 Разрешать attribute mappings только к existing values в selected template lines; собирать полную standard combination, отклонять missing/ambiguous/excluded/archived/non-dynamic missing combinations.
- [x] 4.4 Переиспользовать existing variant или создавать standard dynamic variant после explicit create-access check; записывать mapped internal reference/barcode на новый variant и не менять attribute catalog/template lines.

## 5. Supplier prices и атомарное заполнение пустого PO

- [x] 5.1 Сформировать exact supplierinfo key `(commercial_partner, variant, company, PO currency, line UoM, min_qty)`, использовать `min_qty = 0` по умолчанию и выявлять file price conflicts/duplicate existing keys до apply.
- [x] 5.2 Реализовать batch create/update exact variant-specific `product.supplierinfo`, не меняя unrelated tiers; supplier code/name менять только из mapped values.
- [x] 5.3 Перед apply повторить state/access/company/empty-order/parser/mapping/row/stale validation, не доверяя transient preview как business source of truth.
- [x] 5.4 Одной ORM-транзакцией создать planned products/variants, upsert supplier prices и добавить PO lines через `Command.create()` в source order без unlink/`Command.clear()`, сохраняя шапку и стандартные tax/date/description defaults.
- [x] 5.5 Сохранить all-or-nothing поведение без manual commits и partial success; failed apply оставляет PO пустым, retry создаёт состав один раз, а successful apply блокирует повторный импорт.

## 6. Focused automated tests

- [x] 6.1 Добавить parser/profile/mapping tests для CSV и XLSX: worksheet/header/data rows, physical row numbering, merged headers, blank-row boundary, invalid/empty/oversized input, required/duplicate mappings, read-only preview и stale invalidation; реальную supplier XLSX fixture использовать как regression case.
- [x] 6.2 Добавить product-resolution tests для ordered supplier/default-code/barcode lookup, ambiguity/unmatched policy, standalone defaults/name, existing/dynamic variant, invalid combination и unchanged attribute configuration.
- [x] 6.3 Обновить supplierinfo/apply tests для empty-order population, source order, header preservation, forced rollback с пустым PO, retry и запрета repeat apply без регрессии exact-key сценариев.
- [x] 6.4 Добавить lifecycle tests отказа на open/parse/preview/apply для любой существующей product/section/note строки; сохранить security/multi-company проверки.
- [x] 6.5 Добавить regression test: PO без custom import по-прежнему создаётся, подтверждается и передаётся в standard stock/invoice flow.

## 7. Валидация поставки

- [x] 7.1 Проверить Python syntax/imports, manifest dependencies/data order, XML/external IDs/inheritance targets, ACL CSV, record rules и отсутствие ненужных migrations.
- [x] 7.2 Перечитать фактические `db_name`/`addons_path` из `/etc/odoo/odoo.conf`, обновить `purchase_import` в `odoo_tire` через temporary Odoo на порту 8077 и запустить focused server-side tests.
- [x] 7.3 Выполнить non-browser smoke-проверку empty-order action, compiled views, wizard states и отсутствия destructive confirmation; явно отметить browser behavior как не проверенное автоматически.
- [x] 7.4 Валидировать OpenSpec change и сверить фактическое поведение со всеми 39 Scenarios перед архивированием.
