/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

const MODEL = "stock.dynamic.turnover.report";
const FILTERS = [
    ["product_ids", _t("Products")], ["category_ids", _t("Categories")],
    ["warehouse_ids", _t("Warehouses")], ["location_ids", _t("Locations")],
    ["receipt_ids", _t("Receipts")], ["purchase_order_ids", _t("Purchase orders")],
];
const OPERATIONS = {
    historical_writeoff: _t("Historical write-off"),
    scrap: _t("Scrap"),
    internal_transfer: _t("Internal transfer"),
    customer_return: _t("Customer return"),
    supplier_return: _t("Supplier return"),
    inventory_gain: _t("Inventory gain"),
    inventory_loss: _t("Inventory loss"),
    pos_sale: _t("POS sale"),
    sale_delivery: _t("Sales delivery"),
    supplier_receipt: _t("Supplier receipt"),
    other: _t("Other"),
};

const DIAGNOSTICS = {
    missing_lot_valuation_basis: _t("A valuation lot basis is unavailable."),
    missing_company_valuation_basis: _t("A company valuation basis is unavailable."),
    missing_historical_basis: _t("A historical cost basis is unavailable."),
    standard_quantity_mismatch: _t("Recorded quantity differs from standard valuation quantity."),
    zero_movement_denominator: _t("A valued movement has no owned quantity."),
    missing_internal_valuation_basis: _t("The pre-transfer cost basis is unavailable."),
    missing_valuation_lot: _t("A valuation lot is missing."),
    fifo_stack_quantity_mismatch: _t("FIFO receipts do not match company stock quantity."),
    ambiguous_same_time: _t("Receipt and issue at the same time cannot be ordered reliably."),
    insufficient_fifo_history: _t("FIFO history cannot cover the recorded issue."),
    zero_receipt_denominator: _t("A receipt has no valued quantity."),
    mixed_negative_fifo_basis: _t("FIFO cost weights contain mixed positive and negative values."),
    negative_fifo_basis: _t("FIFO cost weights are negative."),
    zero_cost_fifo_basis: _t("Zero FIFO cost basis was allocated by quantity."),
    fifo_reconciliation: _t("FIFO receipt quantities do not reconcile."),
    receipt_value_vs_standard: _t("Receipt cost basis differs from standard valuation."),
    filtered_attribution_incomplete: _t("Selected PO totals exclude unattributed movements."),
    not_applicable: _t("FIFO does not apply to this product."),
};

export class StockDynamicTurnover extends Component {
    static template = "stock_dynamic_turnover_report.StockDynamicTurnover";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            options: {}, report: null, details: null, loading: false,
            companies: [], queries: {}, suggestions: {}, selectedNames: {}, expanded: {},
        });
        onWillStart(async () => {
            await this.load({});
            const ids = user.context.allowed_company_ids || [];
            this.state.companies = await this.orm.searchRead(
                "res.company", [["id", "in", ids]], ["name"], { limit: 100 });
        });
    }

    get filterChoices() {
        return FILTERS.filter(([key]) => this.state.options.mode === "receipts"
            ? !["warehouse_ids", "location_ids"].includes(key)
            : !["receipt_ids", "purchase_order_ids"].includes(key));
    }

    get dimensions() {
        return this.state.options.mode === "receipts"
            ? [["receipt", _t("Receipt")], ["product", _t("Product")], ["category", _t("Category")]]
            : [["warehouse", _t("Warehouse")], ["location", _t("Location")],
               ["product", _t("Product")], ["category", _t("Category")]];
    }

    get visibleRows() {
        if (!this.state.report) {
            return [];
        }
        return this.state.report.rows.filter((row) => {
            for (let depth = 1; depth < row.level; depth++) {
                if (!this.state.expanded[JSON.stringify(row.path.slice(0, depth))]) {
                    return false;
                }
            }
            return true;
        });
    }

    get operationLabels() {
        return OPERATIONS;
    }

    get quantityLabel() {
        return _t("quantity");
    }

    get valueLabel() {
        return _t("value");
    }

    async load(options) {
        this.state.loading = true;
        this.state.details = null;
        try {
            const report = await this.orm.call(MODEL, "get_report", [options]);
            this.state.report = report;
            this.state.options = { ...report.options };
            this.state.expanded = Object.fromEntries(report.rows.map((row) => [row.key, true]));
        } catch (error) {
            this.notification.add(error.message || _t("Unable to calculate stock turnover."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async apply() {
        const options = { ...this.state.options, page: 1 };
        delete options.cutoff;
        await this.load(options);
    }

    async refresh() {
        await this.apply();
    }

    onDate(event) {
        this.state.options[event.target.name] = event.target.value;
    }

    onCompany(event) {
        this.state.options.company_id = Number(event.target.value);
        for (const [key] of FILTERS) {
            this.state.options[key] = [];
        }
        this.state.selectedNames = {};
    }

    onMode(event) {
        const mode = event.target.value;
        const incompatibleDimensions = mode === "receipts" ? ["warehouse", "location"] : ["receipt"];
        const incompatibleFilters = mode === "receipts"
            ? ["warehouse_ids", "location_ids"] : ["receipt_ids", "purchase_order_ids"];
        if (this.state.options.row_dimensions.some((dimension) => incompatibleDimensions.includes(dimension))
            || incompatibleFilters.some((key) => (this.state.options[key] || []).length)) {
            this.notification.add(_t("Remove incompatible dimensions and filters before changing mode."), {
                type: "warning",
            });
            event.target.value = this.state.options.mode;
            return;
        }
        this.state.options.mode = mode;
    }

    onColumns(event) {
        this.state.options.columns = event.target.value;
    }

    onChildren(event) {
        this.state.options.include_children = event.target.checked;
    }

    toggleDimension(dimension) {
        const dimensions = [...this.state.options.row_dimensions];
        const index = dimensions.indexOf(dimension);
        if (index >= 0) {
            dimensions.splice(index, 1);
        } else {
            dimensions.push(dimension);
        }
        this.state.options.row_dimensions = dimensions;
    }

    moveDimension(dimension, offset) {
        const dimensions = [...this.state.options.row_dimensions];
        const index = dimensions.indexOf(dimension);
        const target = index + offset;
        if (index >= 0 && target >= 0 && target < dimensions.length) {
            [dimensions[index], dimensions[target]] = [dimensions[target], dimensions[index]];
            this.state.options.row_dimensions = dimensions;
        }
    }

    async searchFilter(key, event) {
        const term = event.target.value;
        this.state.queries[key] = term;
        if (term.length < 2) {
            this.state.suggestions[key] = [];
            return;
        }
        try {
            this.state.suggestions[key] = await this.orm.call(
                MODEL, "get_filter_values", [this.state.options, key, term, 30]);
        } catch (error) {
            this.notification.add(error.message || _t("Unable to search report filters."), {
                type: "warning",
            });
        }
    }

    addFilter(key, item) {
        const ids = this.state.options[key] || [];
        if (!ids.includes(item.id)) {
            this.state.options[key] = [...ids, item.id];
        }
        this.state.selectedNames[key + ":" + item.id] = item.name;
        this.state.queries[key] = "";
        this.state.suggestions[key] = [];
    }

    removeFilter(key, id) {
        this.state.options[key] = this.state.options[key].filter((value) => value !== id);
    }

    async changePage(offset) {
        const page = this.state.options.page + offset;
        if (page >= 1 && page <= this.state.report.page_count) {
            await this.load({ ...this.state.options, page });
        }
    }

    toggleRow(row) {
        this.state.expanded[row.key] = !this.state.expanded[row.key];
    }

    diagnosticLabel(code) {
        return DIAGNOSTICS[code] || code;
    }

    formatNumber(value) {
        return value === null || value === undefined
            ? _t("Unavailable")
            : new Intl.NumberFormat(user.lang || "en", { maximumFractionDigits: 4 }).format(value);
    }

    formatQuantity(values) {
        return Object.entries(values || {}).map(([unitId, quantity]) =>
            this.formatNumber(quantity) + " " + (this.state.report.units[unitId] || "")).join("; ") || "0";
    }

    formatMoney(value) {
        if (value === null || value === undefined) {
            return _t("Unavailable");
        }
        return new Intl.NumberFormat(user.lang || "en", {
            style: "currency", currency: this.state.report.currency.name,
        }).format(value);
    }

    async openDetails(row, column) {
        try {
            this.state.details = await this.orm.call(
                MODEL, "get_details",
                [this.state.report.options, row.key, column, this.state.report.revision]);
        } catch (error) {
            this.notification.add(error.message || _t("Refresh the report."), { type: "warning" });
        }
    }

    openDocument(event) {
        if (!event.document_model || !event.document_id) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window", res_model: event.document_model,
            res_id: event.document_id, views: [[false, "form"]], target: "current",
        });
    }

    async exportXlsx() {
        try {
            await download({
                url: "/xlsx_report",
                data: {
                    model: MODEL,
                    data: JSON.stringify({
                        options: this.state.report.options,
                        revision: this.state.report.revision,
                    }),
                    output_format: "xlsx",
                    report_name: "Stock Turnover",
                    report_action: "stock_dynamic_turnover_report.action_stock_dynamic_turnover",
                },
            });
        } catch (error) {
            this.notification.add(error.message || _t("Unable to export stock turnover."), {
                type: "warning",
            });
        }
    }
}

registry.category("actions").add("stock_dynamic_turnover", StockDynamicTurnover);
