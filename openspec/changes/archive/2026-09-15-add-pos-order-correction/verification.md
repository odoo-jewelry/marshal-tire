# Проверка add-pos-order-correction

Дата: 15 сентября 2026 года. Среда: установленный Odoo 19.0 Community.

## Результат

Реализован модуль `main/pos_order_correction`. Административное исправление
сохраняет исходную продажу и создаёт стандартный заказ на товарную и платёжную
разницу. Склад, закрытие смены, поздний счёт, обычный возврат и задолженность
используют стандартные операции Odoo и расширения `pos_customer_debt`.

Все 38 задач выполнены с указанными ниже ограничениями условных ручных
проверок. Итоговые числа и журналы приведены ниже. Браузер и реальный исторический
пример агрегированного списания не проверены; это ограничения проверки,
а не исключение соответствующих требований из реализации.

## Изменённые файлы и решения

Все пути модуля ниже относятся к `main/pos_order_correction/`.

| Файлы | Результат |
|---|---|
| `__manifest__.py`, `__init__.py`, `models/__init__.py` | Новый модуль с зависимостями `point_of_sale`, `pos_customer_debt`; декларативная установка |
| `models/pos_order_correction.py` | Ревизии, строки подготовки, причина, снимки, налоговый и платёжный расчёт, применение в общей транзакции |
| `models/pos_order.py`, `pos_order_line.py`, `pos_payment.py` | Допуск, текущие источники, блокировки, повторный запрос, защита исходных и служебных записей, поздний счёт и возврат |
| `models/stock_picking.py` | Только физическая разница; точные источники, партии/серии, стоимость, невыполненный спрос и агрегирование при закрытии |
| `models/pos_session.py`, `payment_debt_allocation.py` | Учёт разницы текущей сменой и единая цель задолженности корневой продажи |
| `models/correction_integrity.py`, `utils.py` | Защита складских и бухгалтерских следствий; внутренний маркер проверяется по идентичности объекта, клиентский контекст не даёт обхода |
| `models/pos_order_projection.py`, `views/*.xml` | Текущая продажа отдельно от исходных строк/оплат, история с ограничением по корню, ожидание склада и бухгалтерии |
| `models/pos_order_ticket_data.py`, `static/src/ticket_screen.js`, `static/src/ticket_screen.xml` | Существующий экран обычного возврата получает действующие строки всех ревизий; исходный чек и его строки сохраняются |
| `security/*.xml`, `security/ir.model.access.csv` | Выделенная группа исправления, права трёх новых моделей и правила компаний; без общего повышения прав сервиса |
| `i18n/ru.po` | Русские переводы новых полей, действий и сообщений |
| `tests/common.py`, `tests/test_correction_*.py`, `tests/__init__.py` | Серверные проверки редактирования, оплат, склада, долга, жизненного цикла, отчётности, доступа и реальной конкуренции |

В каталоге изменения OpenSpec актуализированы `design.md`, `estimate.md`,
`tasks.md` и этот отчёт. Канонические спецификации и производная документация
не менялись: их синхронизация относится к следующему этапу. Посторонние
существовавшие изменения рабочего дерева сохранены.

### Существенные особенности

- Подготовка разрешена и без открытой смены; применение требует открытую смену
  той же кассы и компании. Закрытая исходная смена не перепроводится.
- Денежное исправление товара сохраняет его физическое происхождение и
  историческую стоимость. Последующая замена или обычный возврат использует
  фактическую отгрузку, включая источники из нескольких ревизий.
- Налоги, округление и сдача проверяются для всей желаемой продажи. Налоговая
  позиция применяется один раз стандартным `map_tax`, в том числе при
  предварительном расчёте на виртуальных записях.
- Внутренние зачёты исправления относятся только к корневой продаже. История
  внешнего погашения остаётся запретом допуска даже после отмены погашения
  или удаления сопоставления. Обычный возврат также блокирует исправление
  после своей отмены.
- Поздний счёт собирает всю цепочку стандартным пакетным механизмом Odoo.
  Оплаты, выручка и долг не признаются повторно.
- Проверка конкуренции использует отдельные реальные соединения с базой:
  применение конкурирует с другим применением, закрытием, счётом, возвратом
  и погашением. Дополнительно проверены изменение партнёра бухгалтерской
  строки, присвоение ей источника оплаты и её удаление: всего восемь
  конкурирующих действий. Операционные транзакции откатываются, собственная
  подготовка теста удаляется.

## Выполненные проверки

### Серверные тесты

Итоговый общий прогон окончательного кода обоих модулей: **118 тестов,
0 ошибок** (81 тест исправлений и 37 тестов задолженности).

```bash
odoo --http-port=8077 -c /etc/odoo/odoo.conf -d odoo_tire_testing \
  -u pos_order_correction,pos_customer_debt --test-enable \
  --test-tags /pos_order_correction,/pos_customer_debt --stop-after-init \
  --logfile=/tmp/add-pos-order-correction-accepted-tests.log
```

Прогон включает налоговую позицию, отменённый обычный возврат, поддельный
клиентский контекст, все 20 складских тестов, восемь реальных конфликтов
транзакций, проверку неоднозначного бухгалтерского источника, фактическое
погашение цепочки 100 + 20, чужую кассу/компанию, смену валюты после подготовки
и прямые запросы возврата устаревших или избыточных количеств.

### Установка и обновление

Чистая база `odoo_tire_testing_testing` создана отдельно для проверки установки.
Использован фактический `addons_path` из `/etc/odoo/odoo.conf`, без его
переопределения, с явными `-d`, `-c`, `--http-port` и `--stop-after-init`.

- Первая установка `-i pos_order_correction --without-demo=all` прошла;
  журнал `/tmp/add-pos-order-correction-install.log`.
- Повторное обновление `-u pos_order_correction,pos_customer_debt` прошло;
  журнал `/tmp/add-pos-order-correction-repeat-upgrade.log`.
- После установки и после обновления количество `pos.order`,
  `pos.order.correction` и `account.move` равно **0 / 0 / 0**.
  Оба модуля имеют состояние `installed`, версию `19.0.1.0.0`.
- Затем в той же отдельной базе штатными действиями создан исторический
  пример: товарная продажа на 30 USD, наличная оплата, выполненная отгрузка,
  закрытая смена и проведённый бухгалтерский документ. После очередного
  обновления обоих модулей сохранены **все значения снимка 23 моделей и
  752 сохраняемых полей**, а также количества записей. Новых исправлений нет.
  Снимки `/tmp/pos-correction-upgrade-before.json` и
  `/tmp/pos-correction-upgrade-after.json` имеют одинаковый SHA256
  `a9845d3b9134321ef5744ca915b4ea613b3b16e6bcb6e0bfdf39e23dd6e0e170`.
  Отчёт сравнения: `/tmp/pos-correction-upgrade-comparison.json`;
  журнал: `/tmp/pos-correction-upgrade-history-update.log`.

### Статические проверки

- Разбор всех файлов Python и XML, синтаксис JavaScript через `node --check`.
- Пути манифеста, зависимости, порядок данных, шесть записей ACL; внешние
  идентификаторы и наследуемые представления также проверены загрузкой Odoo.
- Все 245 строк русского каталога сопоставлены с экспортом Odoo;
  форматы проверены Babel, задано русское правило множественного числа.
- `git diff --check` и `openspec validate add-pos-order-correction --strict`.
  `openspec instructions apply` возвращает `all_done`, 38/38 задач.
  CLI отдельно сообщает о существующем неверном типе `rules.estimate`
  и игнорирует эти правила; конфигурация OpenSpec в рамках изменения
  не менялась. Документ оценки прочитан и актуализирован непосредственно.

Пакеты, инструменты и зависимости не устанавливались. Браузерные
автоматические тесты не создавались и не запускались.

## Соответствие 44 сценариям

Все указанные методы находятся в `main/pos_order_correction/tests/`.
В таблице опущен общий префикс метода `test_`. Несколько вариантов внутри
одного метода проверяют разные ветви одного сценария.

| Сценарий | Файл / методы и проверяемый результат |
|---|---|
| S01 | `test_correction_editing.py`: `prepare_cancel_and_apply_price_change` — подготовка оплаченной продажи открытой смены |
| S02 | `test_correction_lifecycle.py`: `closed_sale_can_be_prepared_without_open_session` — закрытая исходная смена сохраняется |
| S03 | `test_correction_lifecycle.py`: `invoice_created_after_preparation_blocks_apply`, `ordinary_return_created_after_preparation_blocks_apply`, `cancelled_ordinary_return_keeps_history_ineligible`; `test_correction_debt.py`: `cancelled_settlement_still_blocks_correction`; `test_correction_security.py`: `removed_external_matching_still_blocks_correction` |
| S04 | `test_correction_editing.py`: `draft_cancelled_and_return_orders_are_ineligible`; `test_correction_stock.py`: `unprovable_stock_source_is_rejected_during_preparation`; `test_correction_debt.py`: `missing_accounting_source_blocks_preparation`, `contradictory_accounting_source_blocks_preparation` |
| S05 | `test_correction_editing.py`: `prepare_cancel_and_apply_price_change` — отмена подготовки без операционного документа |
| S06 | `test_correction_editing.py`: `reason_and_noop_are_rejected` — обязательная непустая причина |
| S07 | `test_correction_editing.py`: `reason_and_noop_are_rejected` — пустая разница отклоняется |
| S08 | `test_correction_security.py`: `invalid_values_and_foreign_source_are_rejected`, `duplicate_source_is_rejected`, `non_finite_values_are_rejected`, `import_cannot_forge_application_results`; складские тесты партий/серий |
| S09 | `test_correction_stock.py`: `product_replacement_moves_only_difference` — возврат A и отгрузка B с источником |
| S10 | `test_correction_editing.py`: `unchanged_product_is_not_offset` — неизменённая строка остаётся исходной |
| S11 | `test_correction_stock.py`: `quantity_decrease_returns_only_delta`, `quantity_increase_then_return_uses_both_deliveries` |
| S12 | `test_correction_editing.py`: `prepare_cancel_and_apply_price_change`; `test_correction_stock.py`: `avco_return_and_chain_margin_preserve_historical_cost` — цена без склада, сохранение стоимости |
| S13 | `test_correction_stock.py`: `same_session_closing_moves_final_product_once`, `closing_price_then_replacement_moves_only_final_product`, `closing_two_revisions_of_closed_source_do_not_move_intermediate_product` |
| S14 | `test_correction_stock.py`: `serial_decrease_returns_only_removed_serial`, `lot_change_moves_old_and_new_lots_without_quantity_change`, `pending_serial_decrease_preserves_remaining_reservations` |
| S15 | `test_correction_payment.py`: `cash_to_bank_creates_zero_product_order` — нулевой заказ, наличные −100 / банк +100 |
| S16 | `test_correction_payment.py`: `split_payment_records_only_method_differences` — наличные −50 / банк +50 |
| S17 | `test_correction_payment.py`: `unmatched_total_rolls_back_all_documents` — недостаточное распределение без частичного результата |
| S18 | `test_correction_payment.py`: `terminal_registration_change_is_rejected`, `bank_to_cash_preserves_original_payment_evidence` |
| S19 | `test_correction_payment.py`: `closed_session_payment_change_posts_cash_and_bank_difference` — бухгалтерская разница новой смены |
| S20 | `test_correction_lifecycle.py`: `closed_sale_can_be_prepared_without_open_session`; `test_correction_security.py`: `closed_target_session_is_rejected` |
| S21 | `test_correction_editing.py`: `prepare_cancel_and_apply_price_change` — признак ожидания и текущая проекция; XML формы проверен загрузкой |
| S22 | `test_correction_reporting.py`: `sales_and_accounting_keep_original_period_and_post_only_difference` — суммы `report.pos.order` и проведённых бухгалтерских строк двух периодов |
| S23 | `test_correction_debt.py`: `debt_to_cash_reconciles_inside_root_chain`, `internal_debt_credit_allows_a_second_correction` |
| S24 | `test_correction_debt.py`: `debt_increase_has_one_target_and_keeps_other_sale`, `debt_reduction_credit_does_not_consume_new_invoice`, `settlement_consumes_only_corrected_root_sources` — погашение источников 100 + 20, долги других продаж обоих покупателей сохраняются |
| S25 | `test_correction_debt.py`: `debt_increase_has_one_target_and_keeps_other_sale` — запрет погашения до закрытия и разрешение после |
| S26 | `test_correction_stock.py`: `stock_failure_rolls_back_operational_documents`; `test_correction_payment.py`: `unmatched_total_rolls_back_all_documents` |
| S27 | `test_correction_lifecycle.py`: `repeated_apply_returns_same_order` — один операционный результат |
| S28 | `test_correction_security.py`: `stale_draft_is_rejected`, `source_child_change_invalidates_preparation`; `test_correction_debt.py`: `accounting_source_lost_after_preparation_blocks_application`; `test_correction_lifecycle.py`: `currency_change_after_preparation_is_rejected`; тесты счёта/возврата после подготовки; `test_correction_concurrency.py`: `apply_serializes_competing_operational_actions` |
| S29 | `test_correction_security.py`: `batch_failure_rolls_back_first_correction` — ошибка второй ревизии откатывает первую |
| S30 | `test_correction_editing.py`: `prepare_cancel_and_apply_price_change` — снимки, исходные данные, проекция и область действия истории; переходы браузера не проверены |
| S31 | `test_correction_editing.py`: `second_revision_uses_current_projection`; складские тесты нескольких ревизий |
| S32 | `test_correction_security.py`: `applied_records_are_immutable`, `applied_children_cannot_be_created_or_reparented`, `operational_children_cannot_be_added_or_reparented`, `completed_stock_effects_cannot_be_rewritten`, `correction_accounting_cannot_be_reset_or_rewritten` |
| S33 | `test_correction_security.py`: `cashier_cannot_prepare_correction`, `import_cannot_forge_application_results`, `correction_permission_does_not_grant_stock_move_line_access`; `test_correction_stock.py`: `client_context_cannot_override_stock_quantities_or_sources` |
| S34 | `test_correction_security.py`: `invalid_values_and_foreign_source_are_rejected`, `foreign_company_product_is_rejected_on_draft_write`; `test_correction_lifecycle.py`: `other_pos_target_session_is_rejected`, `other_company_target_session_is_rejected` — чужие источники, кассы и компании |
| S35 | 37 тестов `pos_customer_debt`; `test_correction_stock.py`: `closing_preserves_unrelated_ordinary_return`; `test_correction_debt.py`: `correction_session_can_be_closed_by_a_cashier`; обычные продажи/счета/возвраты в подготовке примеров |
| S36 | `test_correction_lifecycle.py`: `late_invoice_uses_effective_result`, `two_correction_sessions_invoice_only_current_products`; `test_correction_debt.py`: `debt_reduction_credit_does_not_consume_new_invoice`, `increased_debt_invoice_transfers_each_session_source` |
| S37 | `test_correction_lifecycle.py`: `return_uses_effective_line_and_blocks_more_corrections`, `pos_data_and_return_preserve_mixed_effective_sources`, `direct_and_pos_returns_reject_stale_or_excessive_sources` — отказы прямого создания и `sync_from_ui` для заменённых строк и избыточного количества; `test_correction_stock.py`: `ordinary_return_after_price_correction_preserves_historical_move`, `quantity_increase_then_return_uses_both_deliveries` |
| S38 | `test_correction_lifecycle.py`: `late_invoice_uses_effective_result`, `return_uses_effective_line_and_blocks_more_corrections`, `direct_invoice_entry_waits_for_correction_closure` |
| S39 | Первая установка, повторное обновление и сверка базы, описанные выше |
| S40 | `test_correction_editing.py`: `second_revision_uses_current_projection`, `empty_sale_can_be_restored_by_a_new_revision` — восстановление новой ревизией |
| S41 | `test_correction_stock.py`: `undelivered_quantity_reduces_pending_demand`, `partial_delivery_decrease_only_reduces_backorder`, `pending_delivery_increase_keeps_additional_demand_pending`, `pending_replacement_retains_shipping_date_and_demand` |
| S42 | `test_correction_payment.py`: `tax_inclusive_price_and_product_replacement`, `original_cash_change_is_not_repeated`, `cash_rounding_validates_full_desired_distribution`, `replacement_applies_fiscal_position_once` |
| S43 | `test_correction_stock.py`: `replacement_after_price_correction_uses_original_move`, `ordinary_return_after_price_correction_preserves_historical_move`, `avco_return_and_chain_margin_preserve_historical_cost` |
| S44 | `test_correction_debt.py`: `cash_to_debt_creates_one_root_debt` — одна цель долга у исходной продажи |

## Ограничения проверки

1. **Ручная проверка браузера не выполнена.** Доступного браузерного инструмента
   нет. Проверены серверные действия, загружаемые данные кассы, XML и синтаксис
   JavaScript; это не подтверждает фактическое отображение и взаимодействие
   формы/экрана возврата в браузере.
2. **Реальный исторический пример агрегированного списания не проверен.**
   В доступной рабочей базе `odoo_tire` обнаружена одна завершённая продажа
   закрытой смены, но нет продаж с `update_stock_at_closing`. База прочитана
   без изменений. Агрегированное списание и отчёт двух периодов проверены
   на специально созданных серверных примерах; они не заменяют такую сверку
   на реальной истории.
3. Рабочая база `odoo_tire` не обновлялась. Установка и выполнение тестов
   относятся только к указанным тестовым базам. Коммит и архивирование
   изменения на этапе применения не выполнялись.
