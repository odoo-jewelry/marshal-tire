## 1. Хранимые снимки и вычисления строки

- [x] 1.1 Преобразовать `current_purchase_price`, `current_sale_price` и `current_markup` в readonly-in-UI stored snapshot fields с `copy=False`, добавить `price_snapshot_initialized` и обеспечить uninitialized-состояние без неявного backfill.
- [x] 1.2 Реализовать batch-aware заполнение и повторное заполнение снимков eligible-строк из product values в контексте `order.company_id`, включая формулу markup, company default fallback и отсутствие product writes.
- [x] 1.3 Перевести `planned_sale_price` на stored markup, сохранить существующие tax/UoM/currency и ceiling-rounding расчёты, а до инициализации снимка исключить usable planned price и update action.
- [x] 1.4 Добавить precision-aware `price_update_required` строки и order-level агрегированные признаки, сравнивая обе пары цен по rounding валюты компании и исключая display/down-payment строки.
- [x] 1.5 Обеспечить очистку снимков при duplicate и устойчивость заполненного снимка к последующим внешним изменениям product prices.

## 2. Явные действия записи цен

- [x] 2.1 Реализовать идемпотентное действие строки, которое серверно перепроверяет eligibility, initialization и discrepancy, затем без `sudo()` записывает обе рассчитанные цены стандартными product fields в контексте компании заказа.
- [x] 2.2 Реализовать `Update All` для всех differing eligible initialized строк с предварительно зафиксированным payload, порядком `(order, sequence, id)` и безопасным no-op при пустом наборе.
- [x] 2.3 После одиночного и массового update обновлять снимки связанных строк из final product values, корректно отражая конфликты одного продукта и общего sales-price owner вариантов.
- [x] 2.4 Удалить `save_prices` из registry и полностью убрать custom `button_confirm()` hook, сохранив стандартные confirm, double approval, cancel, lock, reset/reconfirm без автоматической записи или отката цен.
- [x] 2.5 Обеспечить работу Fill, line Update и Update All во всех состояниях PO через ORM/API с общей транзакционной атомарностью и стандартными правами строки, продукта и компании.

## 3. Форма Purchase Order и переводы

- [x] 3.1 Добавить в header формы PO object-actions `Fill Current Prices` и `Update All` с availability по наличию eligible/differing строк, без state или locked restriction.
- [x] 3.2 Заменить колонку `save_prices` на строковую кнопку `Update`, доступную по `price_update_required`, и показывать snapshot/calculated поля во всех состояниях узким устойчивым XML inheritance.
- [x] 3.3 Обновить manifest version, POT и русские/украинские переводы для новых действий и изменённых labels/help, не меняя зависимости и data order.

## 4. Focused backend tests

- [x] 4.1 Переработать вычислительные тесты для uninitialized snapshot, Fill/refill/stability, markup/default fallback, company context, коммерческих dependencies и rounding/monetary boundaries.
- [x] 4.2 Добавить тесты line Update и Update All для совпадающих, отличающихся и ineligible строк, deterministic ordering, shared product/template owner, final snapshot refresh и empty-set retry.
- [x] 4.3 Проверить действия в draft, sent, to approve, confirmed, locked и cancelled состояниях, очистку snapshot при copy и отсутствие side effects у confirm, double approval, cancel и reconfirm.
- [x] 4.4 Проверить representative permissions и atomic rollback Fill/line/bulk actions без `sudo()`, multi-company изоляцию reference purchase price и стандартную глобальную семантику sales price.
- [x] 4.5 Сохранить regression coverage неизменности `standard_price`, valuation и lot cost для Standard, AVCO и FIFO.

## 5. Upgrade и итоговая проверка

- [x] 5.1 Проверить Python syntax/imports, XML, XPath/external IDs, manifest/data order и отсутствие ненужных ACL, record rules или migration scripts.
- [x] 5.2 Обновить `purchase_price_control` на явной development DB с фактической конфигурацией Odoo и проверить создание stored snapshot columns, `price_snapshot_initialized=False` для существующих строк и игнорирование прежнего `save_prices` без destructive DB cleanup.
- [x] 5.3 Запустить focused backend suite модуля на отдельном HTTP-порту согласно правилам проекта и устранить регрессии стандартного Purchase lifecycle.
- [x] 5.4 Выполнить ручной non-browser smoke формы PO: обе header-кнопки и строковая кнопка в draft, confirmed, locked и cancelled документах; явно зафиксировать, что browser automation не выполнялась.
