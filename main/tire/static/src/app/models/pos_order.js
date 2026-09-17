import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";

patch(PosOrder.prototype, {
    setPartner(partner) {
        const wasToInvoice = this.to_invoice;
        const result = super.setPartner(...arguments);
        if (
            partner?.is_company &&
            !this.config.auto_invoice_company_customer &&
            !wasToInvoice &&
            this.to_invoice
        ) {
            // Preserve the prior choice without bypassing standard customer updates.
            this.setToInvoice(false);
        }
        return result;
    },
});
