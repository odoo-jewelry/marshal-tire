/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, useState } from "@odoo/owl";

export class ProductStockTurnover extends Component {
    static template = "stock_product_turnover_report.ProductStockTurnover";
    static props = { ...standardActionServiceProps };

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            options: {},
            report: null,
            details: null,
            expandedFifo: {},
            loading: false,
            page: 1,
            pageSize: 50,
            sortField: "name",
            sortReverse: false,
            companies: [],
            warehouses: [],
            suggestions: { location: [], product: [], category: [] },
            query: { location: "", product: "", category: "" },
            labels: { location: "", product: {}, category: {} },
        });
        onWillStart(async () => {
            await this.loadReport({});
            await this.loadBaseChoices();
        });
    }

    async loadBaseChoices() {
        const companyIds = user.context.allowed_company_ids || [];
        this.state.companies = await this.orm.searchRead(
            "res.company", [["id", "in", companyIds]], ["name"], { limit: 1000 }
        );
        await this.loadWarehouses();
    }

    async loadWarehouses() {
        this.state.warehouses = await this.orm.searchRead(
            "stock.warehouse",
            [["company_id", "=", this.state.options.company_id]],
            ["name", "view_location_id"],
            { limit: 1000, context: { active_test: false } }
        );
    }

    async loadReport(options = this.state.options) {
        this.state.loading = true;
        this.state.details = null;
        try {
            const report = await this.orm.call("stock.product.turnover.report", "get_report", [options]);
            this.state.report = report;
            this.state.expandedFifo = Object.fromEntries(
                report.rows.map((row) => [row.product_id, Boolean(report.options.show_fifo_receipts)])
            );
            this.state.options = { ...report.options };
            this.state.page = 1;
        } catch (error) {
            this.notification.add(error.message || _t("Unable to calculate the report."), {
                type: "danger",
            });
        } finally {
            this.state.loading = false;
        }
    }

    async refresh() {
        const options = { ...this.state.options };
        delete options.cutoff;
        await this.loadReport(options);
    }

    async applyFilters() {
        const options = { ...this.state.options };
        delete options.cutoff;
        await this.loadReport(options);
    }

    onDateChange(event) {
        this.state.options[event.target.name] = event.target.value;
    }

    async onCompanyChange(event) {
        this.state.options.company_id = Number(event.target.value);
        this.state.options.warehouse_id = false;
        this.state.options.location_id = false;
        this.state.options.product_ids = [];
        this.state.options.category_ids = [];
        this.state.labels.location = "";
        this.state.labels.product = {};
        this.state.labels.category = {};
        await this.loadWarehouses();
    }

    onWarehouseChange(event) {
        this.state.options.warehouse_id = event.target.value ? Number(event.target.value) : false;
        this.state.options.location_id = false;
        this.state.labels.location = "";
    }

    onChildrenChange(event) {
        this.state.options.include_children = event.target.checked;
    }

    onFifoChange(event) {
        this.state.options.show_fifo_receipts = event.target.checked;
    }

    toggleFifo(row) {
        this.state.expandedFifo[row.product_id] = !this.state.expandedFifo[row.product_id];
    }

    fifoBoundaryLabel(boundary) {
        return boundary === "opening" ? _t("Opening FIFO basis") : _t("Closing FIFO basis");
    }

    async searchSelection(kind, event) {
        const term = event.target.value;
        this.state.query[kind] = term;
        if (term.length < 2) {
            this.state.suggestions[kind] = [];
            return;
        }
        const models = {
            location: "stock.location",
            product: "product.product",
            category: "product.category",
        };
        const domain = [["name", "ilike", term]];
        if (kind === "location") {
            domain.push(["company_id", "=", this.state.options.company_id]);
        }
        if (kind === "product") {
            domain.push(["is_storable", "=", true]);
            domain.push(["company_id", "in", [false, this.state.options.company_id]]);
        }
        const records = await this.orm.searchRead(
            models[kind], domain, ["display_name"], { limit: 20, context: { active_test: false } }
        );
        this.state.suggestions[kind] = records;
    }

    chooseSelection(kind, record) {
        if (kind === "location") {
            this.state.options.location_id = record.id;
            this.state.labels.location = record.display_name;
        } else {
            const key = kind === "product" ? "product_ids" : "category_ids";
            if (!this.state.options[key].includes(record.id)) {
                this.state.options[key] = [...this.state.options[key], record.id];
            }
            this.state.labels[kind][record.id] = record.display_name;
        }
        this.state.query[kind] = "";
        this.state.suggestions[kind] = [];
    }

    removeSelection(kind, id) {
        if (kind === "location") {
            this.state.options.location_id = false;
            this.state.labels.location = "";
            return;
        }
        const key = kind === "product" ? "product_ids" : "category_ids";
        this.state.options[key] = this.state.options[key].filter((value) => value !== id);
        delete this.state.labels[kind][id];
    }

    get sortedRows() {
        if (!this.state.report) {
            return [];
        }
        const rows = [...this.state.report.rows];
        const field = this.state.sortField;
        const direction = this.state.sortReverse ? -1 : 1;
        rows.sort((a, b) => {
            const left = a[field] ?? "";
            const right = b[field] ?? "";
            return direction * (typeof left === "number"
                ? left - right
                : String(left).localeCompare(String(right)));
        });
        return rows;
    }

    get pageRows() {
        const start = (this.state.page - 1) * this.state.pageSize;
        return this.sortedRows.slice(start, start + this.state.pageSize);
    }

    get pageCount() {
        return Math.max(1, Math.ceil(this.sortedRows.length / this.state.pageSize));
    }

    sort(event) {
        const field = event.currentTarget.dataset.field;
        if (this.state.sortField === field) {
            this.state.sortReverse = !this.state.sortReverse;
        } else {
            this.state.sortField = field;
            this.state.sortReverse = false;
        }
        this.state.page = 1;
    }

    formatQuantity(value) {
        return value === null || value === undefined
            ? _t("Unavailable")
            : new Intl.NumberFormat(user.lang || "en", { maximumFractionDigits: 4 }).format(value);
    }

    formatMoney(value) {
        if (value === null || value === undefined) {
            return _t("Unavailable");
        }
        return new Intl.NumberFormat(user.lang || "en", {
            style: "currency",
            currency: this.state.report.currency_name,
        }).format(value);
    }

    sourceLabel(source) {
        const labels = {
            current_quant: _t("Current stock"),
            reversed_completed_crossing: _t("Reversed completed movement"),
            recorded_move: _t("Recorded movement cost"),
            standard_pre_transfer: _t("Standard cost before transfer"),
        };
        return labels[source] || source;
    }

    detailLabel(section) {
        const labels = {
            opening: _t("Opening balance"),
            incoming: _t("Incoming turnover"),
            outgoing: _t("Outgoing turnover"),
            difference: _t("Valuation difference"),
            closing: _t("Closing balance"),
        };
        return labels[section] || section;
    }

    async openDetails(row, section) {
        try {
            this.state.details = await this.orm.call(
                "stock.product.turnover.report", "get_details",
                [this.state.report.options, row.product_id, section, this.state.report.fingerprint]
            );
        } catch (error) {
            this.notification.add(error.message || _t("Refresh the report."), { type: "warning" });
        }
    }

    async openFifoReceipt(row, boundary, receipt) {
        try {
            const document = await this.orm.call(
                "stock.product.turnover.report", "get_fifo_receipt_document",
                [this.state.report.options, row.product_id, boundary, receipt.move_id,
                    receipt.lot_id || 0, this.state.report.fingerprint]
            );
            this.openDocument(document);
        } catch (error) {
            this.notification.add(error.message || _t("Refresh the report."), { type: "warning" });
        }
    }

    openDocument(line) {
        if (!line.document_model || !line.document_id) {
            return;
        }
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: line.document_model,
            res_id: line.document_id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async exportXlsx() {
        if (!this.state.report) {
            return;
        }
        try {
            await download({
                url: "/stock_product_turnover_report/export",
                data: {
                    options: JSON.stringify(this.state.report.options),
                    fingerprint: this.state.report.fingerprint,
                },
            });
        } catch (error) {
            this.notification.add(error.message || _t("Refresh the report."), { type: "warning" });
        }
    }
}

registry.category("actions").add("stock_product_turnover_report", ProductStockTurnover);
