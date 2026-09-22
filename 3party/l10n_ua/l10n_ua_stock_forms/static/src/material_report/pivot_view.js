import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { PivotController } from "@web/views/pivot/pivot_controller";
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { pivotView } from "@web/views/pivot/pivot_view";
import { MaterialReportPeriodRange, materialReportPeriodProps } from "./period_range";
import { materialReportSearchModel } from "./search_model";

/**
 * This file travels in `web.assets_backend_lazy`, because that is where Odoo
 * keeps the pivot (`addons/web/__manifest__.py`,
 * `web/static/src/views/pivot/**`). In the ordinary bundle the import of
 * `@web/views/pivot/*` does not resolve. The bundle loads by itself when the
 * view registry lacks the required js_class (`web/static/src/views/view.js:346`).
 */
export class MaterialReportPivotController extends PivotController {
    static template = "l10n_ua_stock_forms.MaterialReportPivotView";
    static components = { ...PivotController.components, MaterialReportPeriodRange };

    get materialReportPeriodProps() {
        return materialReportPeriodProps(this, async () => {
            // PivotModel.load reads searchParams, so an empty call breaks it;
            // hand back the same parameters the view was loaded with.
            await this.model.load(this.model.searchParams);
            // Re-rendering has to be triggered by hand, and that is not
            // belt-and-braces. The list keeps its model in useState
            // (list_controller.js), so there a change of data pulls a render by
            // itself. The pivot does not wrap its model in useState
            // (pivot_controller.js), and its only signal is notify(), which the
            // useModelWithSampleData wrapper (model.js) emits on onWillStart /
            // onWillUpdateProps. We call load() directly — and then
            // PivotModel._loadData replaces this.data while the view never
            // learns about it and keeps showing the previous period.
            this.model.notify();
        });
    }
}

/**
 * Pivot table of the material report: a cell leads to the movements behind it.
 *
 * The standard drill-through opens the records the cell aggregates, on the
 * same model — here, the rows the report itself produced. There is nothing
 * below a month for it to show, and the list it opens is the report's own,
 * whose search model asks for the collapsed rows while the cell domain carries
 * the monthly ones: the two conditions cannot both hold, so the drill-through
 * always came up empty. The level below the report is in the warehouse, and
 * that is what the server hands back.
 */
export class MaterialReportPivotRenderer extends PivotRenderer {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    async onOpenView(cell, newWindow) {
        if (cell.value === undefined || this.model.metaData.disableLinking) {
            return;
        }
        const action = await this.orm.call(
            this.model.metaData.resModel,
            "action_open_movements",
            [
                this.model.getGroupDomain({
                    rowValues: cell.groupId[0],
                    colValues: cell.groupId[1],
                }),
                // Which measure was clicked is the question being asked:
                // receipts and issues are different sets of documents, and a
                // balance is not a set of documents at all.
                cell.measure,
            ]
        );
        return this.actionService.doAction(action, { newWindow });
    }
}

registry.category("views").add("l10n_ua_material_report_pivot", {
    ...pivotView,
    Controller: MaterialReportPivotController,
    Renderer: MaterialReportPivotRenderer,
    // The pivot needs the monthly rows — the per-month statistics are built
    // from them. pivotView.SearchModel rather than the standard one: the pivot
    // has its own (PivotSearchModel), and replacing it with ours would mean
    // losing it.
    SearchModel: materialReportSearchModel(pivotView.SearchModel, { monthly: true }),
});
