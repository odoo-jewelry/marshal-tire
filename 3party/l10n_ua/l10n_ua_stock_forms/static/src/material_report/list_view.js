import { registry } from "@web/core/registry";
import { SearchModel } from "@web/search/search_model";
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { MaterialReportPeriodRange, materialReportPeriodProps } from "./period_range";
import { materialReportSearchModel } from "./search_model";

export class MaterialReportListController extends ListController {
    static template = "l10n_ua_stock_forms.MaterialReportListView";
    static components = { ...ListController.components, MaterialReportPeriodRange };

    get materialReportPeriodProps() {
        return materialReportPeriodProps(this, () => this.model.load());
    }
}

registry.category("views").add("l10n_ua_material_report_list", {
    ...listView,
    Controller: MaterialReportListController,
    // The list shows the collapsed rows — one per product and place for the
    // whole period. It defines no search model of its own, so wrap the standard one.
    SearchModel: materialReportSearchModel(listView.SearchModel || SearchModel, {
        monthly: false,
    }),
});
