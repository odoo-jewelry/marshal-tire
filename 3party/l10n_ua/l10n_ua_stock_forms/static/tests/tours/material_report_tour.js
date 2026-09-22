import { registry } from "@web/core/registry";

/**
 * The material report driven the way a reader drives it.
 *
 * Everything here lives on the client and cannot be reached from a python
 * test: the period button and its dialog, the print entry under the cog, the
 * way down from a row and from a cell of the pivot table to the movements
 * behind them. Each of those has been broken at least once by a change that
 * looked harmless on the server — a call through a destroyed component, an
 * action without its `views`, a read that answered with an error dialog — and
 * every time it was the reader who found out, because nothing else looked.
 *
 * Printing is asserted as an entry in the cog and not clicked: the click asks
 * wkhtmltopdf for a file, and a report that only runs where a binary is
 * installed is a report that gets skipped. What the click does afterwards is
 * covered on the server, in the printing tests.
 */
registry.category("web_tour.tours").add("l10n_ua_material_report", {
    steps: () => [
        {
            content: "The menu opens the report itself: the list, with rows in it",
            trigger: ".o_l10n_ua_material_report_list_view .o_data_row",
        },
        {
            content: "The period is a button of the control panel, not a filter",
            trigger: ".o_l10n_ua_material_report_period button",
            run: "click",
        },
        {
            content: "It opens a small form with the two dates",
            trigger: ".modal .o_field_widget[name=date_from]",
        },
        {
            content: "Confirming rebuilds the report for that period",
            trigger: ".modal button[name=action_apply_period]",
            run: "click",
        },
        {
            content: "The dialog is gone and the report is on screen again",
            trigger: ".o_l10n_ua_material_report_list_view .o_data_row",
        },
        {
            content: "Printing is under the cog rather than in the header",
            trigger: ".o_cp_action_menus i.fa-cog",
            run: "click",
        },
        {
            content: "and it is there",
            trigger: ".o_l10n_ua_material_report_print",
        },
        {
            content: "leave it be — the click itself belongs to the printing tests",
            trigger: ".o_cp_action_menus i.fa-cog",
            run: "click",
        },
        {
            content: "A row leads down to what moved through it",
            trigger: ".o_data_row button[name=action_view_movements]",
            run: "click",
        },
        {
            content: "and lands on the movements themselves, out of the report",
            trigger: "body:not(:has(.o_l10n_ua_material_report_period)) .o_list_view .o_data_row",
        },
        {
            content: "Back to the report",
            trigger: ".o_back_button",
            run: "click",
        },
        {
            content: "The same report, now as a pivot table",
            trigger: "button.o_switch_view.o_pivot",
            run: "click",
        },
        {
            content: "Its first measure is the opening balance",
            trigger: ".o_pivot_view td.o_pivot_cell_value:first",
            run: "click",
        },
        {
            content:
                "A balance is a state at a moment, so the cell says so instead " +
                "of listing movements that would not add up to it",
            trigger: ".o_notification",
        },
    ],
});
