## 1. Налогонезависимая база и снимки цен

- [x] 1.1 В `purchase.order.line` заменить налогозависимые расчёты единым batch-safe механизмом закупочной базы из `price_unit`, скидки, UoM, валюты компании и `date_order`, исключив `tax_ids` и `_get_stock_move_price_unit()` из логики addon.
- [x] 1.2 Перевести автоматический `planned_sale_price` на новую закупочную базу, сохранив округление вверх, точный ручной override, сброс ручного режима через Fill и uninitialized guard.
- [x] 1.3 Перестроить Fill-снимок на `current_standard_price`, `current_sale_price` и вычисляемый от них `current_markup` с company-specific default fallback, сохранив `copy=False`, права строки и multi-company контекст.
- [x] 1.4 Удалить `current_purchase_price`, `effective_purchase_price`, `valuation_purchase_price`, `effective_cost_method` и `product.last_purchase_price` из модели и всех зависимостей вместе с их legacy-столбцами и значениями.

## 2. Явные действия обновления

- [x] 2.1 Изменить `price_update_required` и line payload: сравнивать Current Sale с New Sale, а для Standard Price — Current Cost с налогонезависимой закупочной базой по точности валюты компании.
- [x] 2.2 Обновлять из строки только `lst_price` и, для Standard Price, company-specific `standard_price`; не писать cost для AVCO/FIFO и не использовать `sudo()`.
- [x] 2.3 Адаптировать `Update All` к новому payload, сохранив фиксацию значений до записи, детерминированный порядок конфликтующих строк, refresh после полного успеха и транзакционный откат.
- [x] 2.4 Проверить, что подтверждение, согласование, отмена, reset, lock/unlock, повторный Update и копирование заказа сохраняют существующие lifecycle-инварианты без неявных записей цен.

## 3. Форма и пользовательские тексты

- [x] 3.1 Обновить наследованную list-форму PO: после стандартного `price_unit` разместить `current_standard_price`, `current_markup`, `current_sale_price`, `planned_sale_price` с подписями `Current Cost`, `Markup`, `Current Sale`, `New Sale`, затем `Update`.
- [x] 3.2 Удалить из формы отдельные добавленные колонки reference/effective purchase и valuation cost, сохранив eligibility/readonly/invisible правила и стандартные `tax_ids` и `Unit Price` без изменений.
- [x] 3.3 Обновить английские исходные строки, help-тексты, POT и переводы `ru.po`/`uk.po`, удалив налоговую семантику и устаревшие пользовательские подписи.

## 4. Безопасное обновление установленной базы

- [x] 4.1 Повысить версию addon и добавить воспроизводимую post-migration, которая пакетно пересчитывает `current_markup` инициализированных подходящих строк из сохранённых Current Cost и Current Sale с fallback компании.
- [x] 4.2 Сохранить в миграции ручной `planned_sale_price`, состояния PO, товары, `tax_ids`, складские и бухгалтерские записи; разрешить стандартной очистке Odoo удалить только legacy-поля addon и не обновлять product prices.
- [x] 4.3 Добавить сфокусированную проверку миграции для обычной наценки, неположительной себестоимости, нескольких компаний, ручного New Sale и повторного безопасного запуска.

## 5. Серверные тесты

- [x] 5.1 Переписать тесты снимка на Current Cost/Current Sale и покрыть cost-based markup, default fallback, стабильность, refresh, non-product/down-payment eligibility и copy behavior.
- [x] 5.2 Покрыть налогонезависимость ненулевым `tax_ids`, отдельно проверив стандартные налоговые суммы Odoo, скидку, UoM, валюту, дату курса и округление New Sale.
- [x] 5.3 Сохранить и адаптировать тесты ручного New Sale: точное значение, неизменная наценка, смена налога и других условий, Fill reset, uninitialized rejection и отсутствие неявной записи товара.
- [x] 5.4 Покрыть line/bulk Update для Standard Price, AVCO и FIFO, одинаковых товаров, повторного вызова, rollback, компании и прав доступа текущего пользователя.
- [x] 5.5 Покрыть отсутствие side effects при confirm/approval/cancel/reset/lock/unlock и сохранение стандартных stock/accounting consequences только при явной записи Standard Price cost.

## 6. Итоговая проверка

- [x] 6.1 Проверить синтаксис Python, XML, XPath/external IDs, manifest/migration ordering, импорты, полные `@api.depends`, POT/PO и отсутствие ссылок активного кода/интерфейса на удалённые legacy-поля.
- [x] 6.2 Статически скомпилировать форму и проверить точный порядок `Unit Price`, `Current Cost`, `Markup`, `Current Sale`, `New Sale`; браузерную автоматизацию не запускать.
- [x] 6.3 Прочитать фактический `/etc/odoo/odoo.conf`, обновить `purchase_price_control` на явной development DB временным Odoo-процессом с `--http-port=8077` или следующим свободным портом и запустить сфокусированный серверный набор тестов.
- [x] 6.4 Проверить upgrade safety на копии базы/тестовой базе: удаление legacy-полей, сохранение остальных business records, корректную новую наценку и отсутствие изменений стандартной налоговой, складской и бухгалтерской логики.
