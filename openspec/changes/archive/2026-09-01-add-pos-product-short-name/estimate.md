# Оценка реализации

## Итог

- Всего сценариев: 7
- Implementation-driving сценариев: 2
- Verification-only сценарии: 5
- Implementation clusters: 2
- Implementation units: 1.5
- Fast path: да
- Эмпирический размер: small
- Производительность: 1 час на implementation unit
- Базовая оценка: 1.5 часа
- Исключительные дополнительные работы: 0 часов
- Итоговая оценка: 1–2 часа
- Уверенность: высокая

Итоговая оценка — реалистичное активное рабочее время мидл Odoo-разработчика от начала анализа до готового и обычно проверенного изменения. Focused-проверка loader, static checks, один module update и обычный non-browser smoke входят в clusters.

## Покрытие сценариев

| Спецификация | Scenario | Классификация | Cluster | Risk flags | Обоснование |
|---|---|---|---|---|---|
| `pos-product-short-name` | Save a short name | implementation-driving | C1 | — | Требует нового хранимого поля и его вывода в форме товара. |
| `pos-product-short-name` | Leave the short name empty | verification-only | C1 | — | Проверяет nullable-семантику того же поля. |
| `pos-product-short-name` | Display a configured short name | implementation-driving | C2 | view-conflict | Требует загрузки поля в POS и узкого QWeb-изменения плитки. |
| `pos-product-short-name` | Fall back to the standard product name | verification-only | C2 | view-conflict | Условная ветка реализуется тем же QWeb-выражением. |
| `pos-product-short-name` | Use an updated value after POS data reload | verification-only | C2 | — | Проверяет штатную повторную загрузку того же поля. |
| `pos-product-short-name` | Print or send a receipt for a product with a short name | verification-only | C2 | — | Проверяет неизменную штатную цепочку `full_product_name`. |
| `pos-product-short-name` | Render a basic receipt for a product with a short name | verification-only | C2 | — | Проверяет ту же цепочку в режиме basic receipt. |

## Implementation clusters

| Cluster | Механизм реализации | Покрываемые сценарии | Units | Обоснование |
|---|---|---|---:|---|
| C1 | Расширение `product.template`: переводимое поле, форма и POS loader | Save a short name; Leave the short name empty | 1 | Законченное локальное расширение одной модели по известным механизмам Odoo. |
| C2 | Узкое QWeb-наследование `ProductScreen` с fallback; проверка неизменного чека | Display a configured short name; Fall back to the standard product name; Use an updated value after POS data reload; Print or send a receipt for a product with a short name; Render a basic receipt for a product with a short name | 0.5 | Небольшое изменение одного известного frontend-шаблона без JS-логики. |

## Проверка структуры спецификаций

### Сценарии, которые следует разделить

- Нет.

### Дублирующиеся или пересекающиеся сценарии

- `Print or send a receipt for a product with a short name` и `Render a basic receipt for a product with a short name` используют один штатный источник `full_product_name`, но раздельно фиксируют обычный и basic-режимы чека; объединять их не требуется.

### Недостающие сценарии

- Нет. В этом UI-only scope нет отдельных validation, cancellation, retry, return или multi-company-переходов.

### Недостаточно определённые или противоречивые сценарии

- Нет. Пустое значение, языковой контекст, область POS-экрана и источник имени чека зафиксированы.

## Расчёт трудозатрат

- Сумма implementation units: 1.5
- Hours per unit: 1
- Базовые часы: 1.5
- Discovery: 0
- Миграция или обработка данных: 0
- Production-like bulk/external coordination/special hardware: 0
- Необычная длительная или ручная проверка: 0
- Другие исключительные конкретные работы: 0
- Итоговый диапазон: 1–2 часа

## Стратегия проверки

### Автоматизированные тесты

- Требуются: одна focused-проверка серверной загрузки POS; браузерные автотесты запрещены правилами проекта.
- Обоснование: loader — единственная production-логика в Python; её дешёво защитить от регрессии.
- Минимальный набор: проверить наличие `pos_short_name` в `_load_pos_data_fields()` и его значения в загружаемой записи товара.

### Module update и smoke verification

- Проверить Python syntax/imports, XML, XPath, manifest assets и i18n-файлы.
- Обновить `tire` на явной development-базе и убедиться в компиляции backend- и POS-шаблонов.
- Вручную проверить плитку с заполненным и пустым сокращением, перезагрузку данных, обычный и basic receipt. Браузерное поведение не будет автоматически проверено.

## Основные факторы сложности

- Нужно согласовать backend-поле, POS loader и frontend-вывод в одном addon.
- Нужно точечно изменить основную POS-плитку, не затронув чек и другие места использования `ProductCard`.

## Риски

| Risk flag | Влияние | Как проверяется или снижается |
|---|---|---|
| `view-conflict` | Изменение upstream-структуры `ProductScreen` может сломать XPath. | Узкий XPath на компонент и компиляция assets при module update. |

Флаги `stock`, `procurement`, `mrp`, `accounting`, `migration`, `bulk`, `external`, `security`, `legacy` и `uncertainty` отсутствуют.

## Предположения

- Сокращение задаётся на `product.template`, общее для вариантов и компаний, но переводимое.
- Под «карточкой в POS» понимается плитка в основном каталоге `ProductScreen`.
- Поиск, корзина, combo-диалоги и preparation receipts сохраняют штатное поведение.

## Исключено из оценки

- Поиск POS по сокращению.
- Вариантные, company-dependent или POS-specific сокращения.
- Изменение корзины, combo-диалогов, preparation receipts, отчётов или счетов.
- Браузерные автотесты и tours.

## Требуется discovery

- Нет.
- Обоснование: стандартные extension points Odoo 19 и существующий владелец addon подтверждены исходным кодом.

## Условия пересмотра оценки

- Сокращение должно стать искомым в POS.
- Поле должно различаться по варианту, компании или POS-конфигурации.
- Сокращение должно появиться в корзине, combo-диалогах или других видах чеков.
- Потребуется нештатная миграция, автозаполнение или массовая обработка.

## Фактический результат

Заполняется после реализации:

- Фактические часы:
- Отклонение от оценки:
- Причина отклонения:
- Фактические часы на unit:
- Изменения для будущей калибровки:
