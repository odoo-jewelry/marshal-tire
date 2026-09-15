## 1. Модель аудита и интерфейс

- [x] 1.1 Добавить явную зависимость `stock_account`, подключить расширение `stock.move` и сохранить уже имеющееся пользовательское изменение автора в manifest без перезаписи.
- [x] 1.2 Добавить защищённые readonly-поля связи входящего движения с исходным FIFO receipt, снимком его даты и парным исходящим движением; запретить их произвольную запись вне проверенного контекста объединения.
- [x] 1.3 Расширить transient preview структурированными полями quantity, value, currency, location, package, source move/date и отобразить их вместе с stock-aware текстом финального подтверждения.
- [x] 1.4 Добавить readonly-аудит переноса в форму `stock.move` и ссылки на созданные движения в итоговое сообщение canonical product.

## 2. Анализ и планирование переноса

- [x] 2.1 Заменить общий blocker ненулевого stock на company-aware сбор положительных внутренних/transit quants с сохранением location/package и отдельные blockers для reservation, inventory count, negative quantity, owner и tracking/lot.
- [x] 2.2 Добавить проверку открытых stock moves дубля и совместимости FIFO/valuation/inventory location/account settings двух карточек только для операций с положительным остатком.
- [x] 2.3 Построить детерминированный transfer plan пересечением remaining FIFO receipt layers и физических location/package buckets; сверить итоговые количества и стоимости с quants и валютным/UoM округлением.
- [x] 2.4 Добавить preview totals/segments и предупреждение для receipt со стоимостью, которую ещё может изменить незавершённое supplier billing; сохранить preview полностью read-only.
- [x] 2.5 Повторно строить весь stock/configuration plan непосредственно в `consolidate()` и отклонять устаревший или несогласованный снимок до любых постоянных изменений.

## 3. Атомарное выполнение складской операции

- [x] 3.1 Зафиксировать затрагиваемые quants в стабильном порядке и повторно проверить quantity, reservation и dimensions, чтобы конкурентное изменение не создало отрицательный или частичный перенос.
- [x] 3.2 Для каждого сегмента создать и завершить стандартное исходящее inventory movement дубля текущей датой с исходными location/package и без прямой записи в `stock.quant`.
- [x] 3.3 Создать парное входящее movement основной карточки в то же location/package, назначить ему фактический `out_move.value` через штатный `value_manual` и записать audit links/source date.
- [x] 3.4 Проверить после всех пар нулевой внутренний остаток дубля, точный прирост количества canonical, допустимое валютное расхождение общей стоимости, состояние `done` и полноту связей.
- [x] 3.5 Включить transfer handler в существующую последовательность до configuration/aliases/archive, сохранив одну транзакцию, существующие права, company isolation, zero-stock path и возможность безопасного retry после rollback.

## 4. Автоматизированная и статическая проверка

- [x] 4.1 Добавить характеристические тесты стандартного Odoo 19 для FIFO remaining layers, `value_manual`, текущей даты `_action_done()` и rollback; подтвердить выбранные extension points до завершения реализации.
- [x] 4.2 Покрыть тестами 5 + 10 = 15, несколько FIFO costs с частичным расходом, существующий canonical stock, сохранение итоговой стоимости и расположение/упаковку.
- [x] 4.3 Покрыть текущую дату и неизменность history, source audit fields, mutable-valuation warning, preview cancellation и zero-stock regression без лишних движений.
- [x] 4.4 Покрыть blockers reservation, negative/unreconciled stock, inventory count, open moves, owner, tracking/lot, valuation mismatch и stale/concurrent state.
- [x] 4.5 Покрыть принудительную ошибку на промежуточном шаге, полный rollback, успешный retry, authorization и same/cross-company behavior.
- [x] 4.6 Проверить неизменность обычных stock/product flows без объединения и существующих функций draft references, aliases, archive и поиска canonical.
- [x] 4.7 Выполнить Python/XML/manifest/external-ID проверки, обновить `product_card_consolidation` на отдельной тестовой БД с обязательным `--http-port=8077`, запустить focused tagged tests и проверить upgrade safety; браузерную автоматизацию не запускать.
