# pos-report-cost-measure Specification

> [!abstract] Себестоимость в анализе заказов точки продаж
> Позволяет сопоставлять суммарную себестоимость продаж и возвратов с выручкой и маржой.
>
> **Использование:**
>
> В приложении «Точка продаж», в отчете анализа заказов, выберите «Себестоимость» в меню мер сводной таблицы или диаграммы. Показатель доступен с существующими фильтрами и группировками по товарам, периодам и точкам продаж. Начальный набор выбранных мер сохраняется; формы заказов и строки чеков не изменяются.
>
> Например, сгруппируйте отчет по товарам для сравнения затрат или ограничьте период и точку продаж для анализа конкретного магазина. При совместном выборе продажи с себестоимостью 80 и частичного возврата с себестоимостью −40 итог составит 40. После изменения сохраненной себестоимости обновите отчет, чтобы увидеть актуальный результат.
>
> Показатель отражает сохраненную себестоимость строк с учетом количества, знака возврата и валютной базы стандартного отчета. При незавершенном расчете показываются имеющиеся значения; отсутствующая себестоимость учитывается как ноль. Действуют стандартные ограничения доступа и компаний, а отмененные заказы исключаются стандартным фильтром.
^feature-card

## Purpose

Allow users to analyze the total saved cost of POS sales and returns alongside existing sales measures using the standard order analysis report.

## Requirements

### Requirement: Selectable total cost measure

POS order analysis SHALL offer a total cost measure in both pivot and graph measure selectors, labelled as the equivalent of “Cost” in the user's language. The Russian label SHALL mean total cost. The measure SHALL sum saved line costs for the current report selection, preserving existing grouping and filtering. Existing initially selected measures SHALL remain unchanged.

#### Scenario: S01 Select and aggregate cost
- **GIVEN** two selected sale lines have saved total costs of 80 and 30 in the report currency
- **WHEN** the user selects the cost measure in pivot analysis
- **THEN** the total is 110
- **AND** grouping by product or period and narrowing filters aggregates only the corresponding lines

#### Scenario: S02 Select cost in graph analysis
- **WHEN** the user opens the graph measure selector
- **THEN** the cost measure is available for selection
- **AND** selecting it displays the same grouped amounts as pivot analysis with equivalent filters and grouping

### Requirement: Saved signed cost and currency consistency

Cost SHALL use the saved total for each line, which already includes quantity. It MUST NOT multiply it by quantity again, replace it with current product cost, or recalculate stock valuation. The measure SHALL preserve the saved sign of return costs. Currency conversion SHALL use the same saved order conversion basis and zero-or-missing-rate fallback as the standard margin measure. Missing costs SHALL contribute zero, consistently with standard margin analysis; incomplete calculation SHALL NOT trigger recalculation or exclusion of a line.

#### Scenario: S03 Report a partial return
- **GIVEN** a two-unit sale has saved cost 80 and its one-unit return has saved cost minus 40 in the same currency
- **WHEN** both orders are included in analysis
- **THEN** their combined cost is 40

#### Scenario: S04 Convert a foreign-currency cost
- **GIVEN** a line has saved cost 160 in order currency and the order's saved conversion rate to report amounts is 2
- **WHEN** the cost measure is read
- **THEN** its report amount is 80, using the same conversion basis as margin

#### Scenario: S05 Use the standard missing-rate fallback
- **GIVEN** an order has zero or missing saved conversion rate and a line cost of 80
- **WHEN** its cost is reported
- **THEN** its cost contribution is 80 without a division error

#### Scenario: S06 Display incomplete saved costs
- **GIVEN** cost calculation is incomplete and a line's saved cost is missing, zero, or a nonzero value
- **WHEN** analysis is refreshed
- **THEN** missing or zero cost contributes zero and a nonzero saved value contributes its converted amount
- **AND** reading the report leaves calculation status and saved costs unchanged

### Requirement: Historical reporting without side effects

Existing orders SHALL become reportable without rewriting their costs during installation or upgrade. Refreshing analysis SHALL reflect subsequent saved cost updates from existing workflows. Repeated reads MUST NOT change costs, orders, payments, accounting or stock records.

#### Scenario: S07 Reflect a saved cost update
- **GIVEN** an existing workflow changes a historical line's saved cost from 0 to 80 in the same currency
- **WHEN** analysis is refreshed repeatedly
- **THEN** the line contributes 80 each time without further changes to source data

#### Scenario: S08 Upgrade with historical orders
- **GIVEN** historical sales and returns already have saved costs
- **WHEN** the reporting addition is installed or upgraded
- **THEN** their costs become available in analysis without historical recomputation

### Requirement: Preserve report access and standard behavior

The measure SHALL follow existing report access rights and allowed-company restrictions, including direct report requests. Existing state filters and measures SHALL retain their behavior. Reporting SHALL use each company's existing report currency semantics without introducing cross-company currency consolidation.

#### Scenario: S09 Preserve company isolation
- **GIVEN** the report contains orders for companies A and B and only company A is allowed in the user's report context
- **WHEN** the user requests grouped cost totals through the interface or directly
- **THEN** orders of company B do not contribute to the result

#### Scenario: S10 Deny unauthorized report access
- **WHEN** a user without report read permission requests cost totals directly
- **THEN** access is denied under the existing report permissions

#### Scenario: S11 Preserve cancellation filtering
- **GIVEN** a cancelled order has a saved cost
- **WHEN** analysis uses the standard default exclusion of cancelled orders
- **THEN** the order is excluded from cost totals
- **AND** removing that filter includes its saved cost under the same rules as other report measures

#### Scenario: S12 Preserve analysis without cost selection
- **WHEN** a user opens analysis without selecting cost
- **THEN** the initially selected measures, grouping, filters and existing measure results remain unchanged
