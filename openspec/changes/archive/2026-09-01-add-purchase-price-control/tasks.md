## 1. Каркас addon и источники данных

- [x] 1.1 Создать installable addon `main/purchase_price_control` с manifest-зависимостями `purchase` и `stock_account`, стандартными init-файлами и детерминированным порядком XML data.
- [x] 1.2 Добавить company-dependent `product.product.last_purchase_price` в валюте компании на базовую UoM, не связывая его с `standard_price` или valuation-моделями.
- [x] 1.3 Добавить в `res.company` шаг округления с default `0.01`, наценку по умолчанию с default `0.0` и серверный constraint положительного шага; опубликовать их writable related-полями `res.config.settings`.
- [x] 1.4 Проверить company isolation новых полей и отсутствие изменений `standard_price`/lot costs для Standard Price, AVCO и FIFO.

## 2. Расчёты price control в строке PO

- [x] 2.1 Добавить batch-aware non-stored информационные поля и `save_prices` с `copy=False`, исключив display, down-payment и иные неeligible строки.
- [x] 2.2 Реализовать effective purchase unit price через стандартный tax engine с текущими `price_unit`, `discount` и `tax_ids`, затем нормализовать purchase UoM и валюту PO к базовой UoM и валюте `order.company_id` на дату заказа.
- [x] 2.3 Реализовать current markup от `last_purchase_price` с fallback на company default и planned sale price с ceiling до настраиваемого шага, безопасным для точных кратных и дробных шагов.
- [x] 2.4 Объявить полные compute/context dependencies и проверить пересчёт после изменения продукта, коммерческих условий, UoM, валюты, даты, компании и настроек.

## 3. Интерфейс Purchase

- [x] 3.1 Узко унаследовать форму PO и показать текущую справочную закупочную цену, продажную цену, наценку, effective purchase price, planned sale price и доступный в `draft`/`sent` флажок `save_prices` в продуктовых строках.
- [x] 3.2 Добавить в Purchase settings блок Price Control с company-dependent полями default markup и rounding step, единицами и примерами значений.
- [x] 3.3 Проверить XML, external IDs, inheritance targets, видимость/readonly выражения и успешную компиляцию обоих views без browser automation.

## 4. Сохранение цен при подтверждении

- [x] 4.1 Расширить batch-вызов `purchase.order.button_confirm`: до `super()` собрать пересчитанный payload только для отмеченных eligible-строк исходных `draft`/`sent` заказов, после успешного `super()` применить его в порядке `(order, sequence, id)`.
- [x] 4.2 Записывать `last_purchase_price` через `with_company(order.company_id)` и planned sales price через стандартный inverse варианта, без `sudo()` и без записи в `standard_price`.
- [x] 4.3 Обеспечить семантику double approval, последней конфликтующей строки, rollback при любой ошибке, повторного confirm после reset to draft и отсутствия отката при cancel.
- [x] 4.4 Проверить, что duplicate очищает `save_prices`, а import/API с явно переданным флажком проходят тот же серверный confirm flow.

## 5. Автоматизированная и интеграционная проверка

- [x] 5.1 Добавить focused tests вычислений: сохранённая/default markup, налоги со скидкой, price-included/price-excluded обработка, purchase UoM, валюта/дата курса и все rounding boundary cases.
- [x] 5.2 Добавить focused lifecycle tests: выбранные/невыбранные и non-product строки, обычный confirm, To Approve, конфликтующие строки/варианты, copy, cancel, reset/reconfirm и atomic failure.
- [x] 5.3 Добавить multi-company и access tests, подтверждающие company-dependent reference price/settings, отсутствие `sudo()` и неизменность valuation cost при всех cost methods.
- [x] 5.4 Выполнить Python syntax/import checks, XML/static validation, обновление addon на явной development DB и focused test suite; отдельно зафиксировать ручной smoke UI и всё, что не удалось проверить.
