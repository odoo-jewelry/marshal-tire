import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

function hasCorrection(order) {
    return Boolean(order?.correction_has_applied && !order.is_correction_order);
}

function refundLines(order) {
    return hasCorrection(order) ? order.correction_current_line_ids : order?.lines || [];
}

// A read-only view used by synchronous selection helpers only. The loaded
// record, inverse line ownership and the receipt data remain unchanged.
function refundSelection(order) {
    if (!hasCorrection(order)) {
        return order;
    }
    return new Proxy(order, {
        get(target, key, receiver) {
            if (key === "lines") {
                return refundLines(target);
            }
            if (key === "getOrderlines") {
                return () => refundLines(target);
            }
            return Reflect.get(target, key, receiver);
        },
    });
}

class CorrectionOrderDisplay extends OrderDisplay {
    static template = "pos_order_correction.CorrectionOrderDisplay";

    get comboSortedLines() {
        if (!hasCorrection(this.order)) {
            return super.comboSortedLines;
        }
        const lines = refundLines(this.order);
        const effectiveIds = new Set(lines.map((line) => line.id));
        return lines.reduce((sorted, line) => {
            const children = line.combo_line_ids.filter((child) => effectiveIds.has(child.id));
            if (children.length) {
                sorted.push(line, ...children);
            } else if (!line.combo_parent_id || !effectiveIds.has(line.combo_parent_id.id)) {
                sorted.push(line);
            }
            return sorted;
        }, []);
    }
}

patch(PosOrder.prototype, {
    initState() {
        super.initState();
        if (this.is_correction_order) {
            this.uiState.displayed = false;
        }
    },

    restoreState(uiState) {
        super.restoreState(uiState);
        if (this.is_correction_order) {
            this.uiState.displayed = false;
        }
    },
});

patch(TicketScreen, {
    components: { ...TicketScreen.components, OrderDisplay: CorrectionOrderDisplay },
});

patch(TicketScreen.prototype, {
    getCorrectionRefundLines(order) {
        return refundLines(order);
    },

    getSelectedOrderlineId() {
        const selectedId = super.getSelectedOrderlineId();
        const order = this.getSelectedOrder();
        if (!hasCorrection(order)) {
            return selectedId;
        }
        const lines = refundLines(order);
        return lines.some((line) => line.id === selectedId) ? selectedId : lines[0]?.id;
    },

    getSelectedOrder() {
        const order = super.getSelectedOrder();
        return this.correctionSelectingQuantity ? refundSelection(order) : order;
    },

    _onUpdateSelectedOrderline(event) {
        this.correctionSelectingQuantity = true;
        try {
            return super._onUpdateSelectedOrderline(event);
        } finally {
            this.correctionSelectingQuantity = false;
        }
    },

    _doesOrderHaveSoleItem(order) {
        return super._doesOrderHaveSoleItem(refundSelection(order));
    },

    _prepareAutoRefundOnOrder(order) {
        if (!hasCorrection(order)) {
            return super._prepareAutoRefundOnOrder(order);
        }
        const line = refundLines(order).find((item) => item.id === this.getSelectedOrderlineId());
        if (!line) {
            return false;
        }
        const detail = this.getToRefundDetail(line);
        if (this.pos.isProductQtyZero(line.qty - line.refundedQty - 1) && detail.qty === 0) {
            detail.qty = 1;
        }
        return true;
    },

    _getRefundableDetails(partner, order) {
        if (!hasCorrection(order)) {
            return super._getRefundableDetails(partner, order);
        }
        const effectiveIds = new Set(refundLines(order).map((line) => line.id));
        return Object.values(this.pos.linesToRefund).filter(
            (refund) => effectiveIds.has(refund.line.id)
                && !this.pos.isProductQtyZero(refund.qty)
                && (!partner || refund.line.order_id.partner_id?.id === partner.id)
                && !refund.destinationOrder
        );
    },

    getHasItemsToRefund() {
        const order = this.getSelectedOrder();
        if (!hasCorrection(order)) {
            return super.getHasItemsToRefund();
        }
        return !order.correction_pending && (
            this._doesOrderHaveSoleItem(order)
            || this._getRefundableDetails(order.getPartner(), order).length > 0
        );
    },

    async onDoRefund() {
        if (this.getSelectedOrder()?.correction_pending) {
            this.dialog.add(AlertDialog, {
                title: _t("Correction is pending"),
                body: _t("Close all correction sessions before returning products."),
            });
            return;
        }
        return await super.onDoRefund();
    },
});
