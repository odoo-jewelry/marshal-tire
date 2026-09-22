import { Domain } from "@web/core/domain";

// Date grouping steps for the material report.
//
// A report row covers a month — the data holds nothing finer. Week and day in
// the Period menu are therefore pointless: grouping by them would give as many
// columns as there are months, only with captions like "W19 2026" that stand
// for nothing. Year, quarter and month are kept — the steps the report really
// distinguishes.
//
// There is nothing to restrict them with short of replacing the search model:
// Odoo takes the intervals from the global INTERVAL_OPTIONS in
// SearchModel.setup (web/search/search_model.js) and offers no arch attribute
// for them.
const HIDDEN_INTERVALS = ["week", "day"];

/**
 * Search model of the material report: its own intervals and its own row
 * granularity.
 *
 * The report rows sit in the database in two granularities at once —
 * collapsed over the whole period and monthly. The list must show the former,
 * the pivot table the latter, and the action is shared by both, so the action
 * domain cannot tell them apart. Hence `monthly`: a view appends the required
 * condition to every domain the search model builds, the left-hand panel's
 * domain included — otherwise its counters would count both granularities.
 *
 * It is taken as a wrapper over a given class because the base models of the
 * views differ: the List runs on the standard SearchModel and the Pivot on
 * PivotSearchModel, and replacing the latter with ours would mean losing what
 * it does. The pivot also lives in the lazy bundle, so stitching both views
 * together is only possible here, in the shared one.
 */
export function materialReportSearchModel(SearchModelClass, { monthly }) {
    return class extends SearchModelClass {
        setup(...args) {
            super.setup(...args);
            this.intervalOptions = this.intervalOptions.filter(
                (option) => !HIDDEN_INTERVALS.includes(option.id)
            );
        }

        _getDomain(params = {}) {
            const domain = Domain.and([
                super._getDomain({ ...params, raw: true }),
                [["is_monthly", "=", monthly]],
            ]);
            return params.raw ? domain : domain.toList(this.domainEvalContext);
        }
    };
}
