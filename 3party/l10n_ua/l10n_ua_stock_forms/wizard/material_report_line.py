"""Rows of the material report as records fit to be browsed.

The PDF prints the form as it is, but people also work with it: they look up
a product, check a category, narrow down to a single storage place, fold it
into totals. So the very rows that go to print are materialized here and shown
in two modes — List (with the category and storage place panels on the left,
like the standard Inventory report) and Pivot table.

A row is "product + storage place + month", not a product alone: the store a
person is in charge of usually consists of several places, and the same
product yields as many rows as the places it sat in. The period, in turn, is
cut into calendar months, so over a quarter the same product in the same place
yields three rows — and that is what the monthly statistics in the pivot table
are built from.

A row's `date_from` is the start of its month (clipped by the period bounds in
the edge months), so grouping by `date_from:month` gives exactly the months of
the report.

These same records are what gets printed: the printed form is built from them
rather than recomputing the report, which is why the filters on screen reach
the paper too.

This is a snapshot of a period, not accounting data: the values are written
once when the report is built and are deliberately not related fields of the
product, so that a later change of its category or price cannot rewrite a
report that has already been produced. The records live exactly as long as the
wizard that produced them.
"""

import babel.dates

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.fields import Domain
from odoo.tools import get_lang

# CLDR distinguishes two spellings of a month name: the "format" one (MMMM),
# for a full date, and the "stand-alone" one (LLLL), for a month on its own.
# In Ukrainian these are different grammatical cases. Odoo groups with
# 'MMMM yyyy' (READ_GROUP_DISPLAY_FORMAT in odoo/orm/models.py); in English
# the two coincide, in Ukrainian the report column ends up in the genitive.
STANDALONE_MONTH_FORMAT = 'LLLL yyyy'

# Measures a set of documents can stand behind, and the end of a move line each
# of them is made of.
#
# Receipts and issues are flows: move lines add up to exactly those numbers, so
# opening the cell can show what it was made of. A balance is a state at a
# moment and has no such set — the movements behind it reach back before the
# report started, and its amount is the quantity at the current price rather
# than the sum of anything. Clicking one therefore explains itself instead of
# showing a plausible list that does not add up to the number above it.
#
# A move line is a receipt for the place it went into and an issue for the
# place it left.
RECEIPT_END = ('location_dest_id',)
ISSUE_END = ('location_id',)

# Both ends at once: everything that moved through the place, whichever way.
# That is what a row of the list can honestly offer — it carries receipts and
# issues side by side, so a single click cannot mean one of them.
MOVEMENT_BOTH_ENDS = RECEIPT_END + ISSUE_END

MOVEMENT_MEASURES = {
    'in_qty': RECEIPT_END,
    'in_value': RECEIPT_END,
    'out_qty': ISSUE_END,
    'out_value': ISSUE_END,
}


class L10nUaMaterialReportLine(models.TransientModel):
    _name = 'l10n_ua.material.report.line'
    _description = 'Material Report Line'
    _order = 'product_id, location_id'
    _rec_name = 'product_id'
    # The rows must outlive the wizard's own vacuum window, or a report on
    # screen would lose its content while its parameters are still there.
    _transient_max_hours = 12

    # One index for the one query both views actually run: the action narrows
    # to a report, the search model to a granularity. Per-column indexes were
    # of no use to it and were not free either — the table is rewritten whole
    # on every change of period, and every index is paid for on each INSERT.
    # The panel counters group over a few hundred rows, where a sequential
    # scan beats an index anyway.
    _wizard_granularity_idx = models.Index('(wizard_id, is_monthly)')

    # The rows are stored in two granularities at once: collapsed over the
    # whole period (for the list and the form) and monthly (for the pivot
    # table). The views tell them apart by this flag — otherwise the pivot
    # would count the same movement twice.
    is_monthly = fields.Boolean(
        string='Monthly Row',
        default=False,
    )
    wizard_id = fields.Many2one(
        'l10n_ua.material.report.wizard',
        string='Report',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        required=True,
        ondelete='cascade',
    )
    default_code = fields.Char(string='Product Reference')
    categ_id = fields.Many2one(
        'product.category',
        string='Product Category',
    )
    uom_id = fields.Many2one('uom.uom', string='UoM')
    # The price is not summed: as a pivot measure it means nothing.
    price = fields.Float(
        string='Cost Price',
        digits='Product Price',
        aggregator=None,
    )

    opening_qty = fields.Float(
        string='Opening Balance', digits='Product Unit')
    opening_value = fields.Monetary(string='Opening Amount')
    in_qty = fields.Float(string='Receipts', digits='Product Unit')
    in_value = fields.Monetary(string='Receipts Amount')
    out_qty = fields.Float(string='Issues', digits='Product Unit')
    out_value = fields.Monetary(string='Issues Amount')
    closing_qty = fields.Float(
        string='Closing Balance', digits='Product Unit')
    closing_value = fields.Monetary(string='Closing Amount')

    # Not the store from the report parameters but the concrete place beneath
    # it: a row is a "product + storage place" pair, and this is the field the
    # search panel narrows on.
    location_id = fields.Many2one(
        'stock.location',
        string='Storage Place',
    )
    date_from = fields.Date(string='Period From')
    date_to = fields.Date(string='Period To')
    company_id = fields.Many2one('res.company', string='Company')
    currency_id = fields.Many2one('res.currency', string='Currency')

    def _web_read_group_groupby_formatter(self, groupby_spec, values):
        """Month name in the nominative case, the way a label should read.

        Only the label is touched; the rest is left to the standard formatter,
        which also builds the group domain — the part that must not break.

        This overrides the model alone rather than READ_GROUP_DISPLAY_FORMAT
        globally: that dict is shared by the whole database, and a warehouse
        reporting module has no business silently renaming months in every
        Odoo report. If the fix is wanted everywhere, it belongs in a base
        Ukrainian localization module, not here.
        """
        formatter = super()._web_read_group_groupby_formatter(groupby_spec, values)
        field_name, _sep, granularity = groupby_spec.partition(':')
        field = self._fields.get(field_name)
        if granularity != 'month' or not field or field.type != 'date':
            return formatter

        locale = get_lang(self.env).code

        def formatter_standalone_month(value):
            result, domain = formatter(value)
            if value:
                raw, _label = result
                result = (raw, babel.dates.format_date(
                    value, format=STANDALONE_MONTH_FORMAT, locale=locale))
            return result, domain

        return formatter_standalone_month

    @api.model
    def action_print_report(self, domain):
        """Print from the cog: exactly what is on screen goes to paper.

        The domain comes from the view, so the control panel filters and the
        narrowing done with the left-hand panel reach the form as well.
        Printing has no dialog of its own — the period and the store are read
        from the rows being printed. What that domain is worth, and why one
        form describes one report, is `_rows_from_client`.

        What goes to paper is the wizard, not these rows: a file named after
        the store and the period beats one named after the action, and Odoo
        only names a file after the record when a single one is printed. The
        chosen rows travel on `printed_line_ids` — see the field for why not
        through the action's `data`.
        """
        lines = self._rows_from_client(
            domain,
            nothing=_('No rows match the current filters, so there is '
                      'nothing to print.'),
            several=_('These rows come from several reports, and one form can '
                      'only describe one. Narrow the selection down to a '
                      'single report.'),
        )
        wizard = lines.wizard_id
        wizard.printed_line_ids = self._collapsed(lines)
        return self.env.ref(
            'l10n_ua_stock_forms.action_report_material_report'
        ).report_action(wizard)

    @api.model
    def action_open_movements(self, domain, measure):
        """What a cell of the pivot table was made of: the movements themselves.

        Odoo's own drill-through opens the records the cell aggregates, which
        here would be the report's own rows — the report has no level below the
        month, so it would show the same numbers again. The level below is in
        the warehouse: the move lines the report counted. That is the question
        a reader actually has at a number — "what makes up these 40?".

        What the domain of the cell is worth is `_rows_from_client`.
        """
        ends = MOVEMENT_MEASURES.get(measure)
        if not ends:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'sticky': False,
                    'message': _(
                        'Movements can be shown for receipts and issues only. '
                        'A balance is what is held at a moment, not something '
                        'that moved.'),
                },
            }
        lines = self._rows_from_client(
            domain,
            nothing=_('The rows of this report are gone — reopen it from the '
                      'menu.'),
            several=_('These rows come from several reports, and their '
                      'movements cannot be shown as one list.'),
        )
        return lines._movements_action(
            ends, _('Receipts') if ends == RECEIPT_END else _('Issues'))

    @api.model
    def _rows_from_client(self, domain, *, nothing, several):
        """The rows a client asked for — as far as they are its to ask for.

        Both ways into this model from a browser hand over a domain: the cog
        gives the one the view is showing, a cell of the pivot table the one it
        stands for. Neither is trusted, because both methods are public and
        anything at all can be handed to them. The record rule already keeps
        other people's reports and other companies' out of reach; the author
        condition here says the same thing at the point where the rows are
        read, rather than leaving the safety of a public method to a rule
        declared in another file.

        One request describes one report. A hand-made call could name rows of
        several at once, and then a form would carry the header of one of them
        over the figures of the others, or a list of movements would run
        together periods that have nothing to do with each other. Better to
        refuse than to hand over something plausible that says the wrong thing.

        The two refusals are worded by the caller: what to do about it depends
        on what was being asked for.
        """
        lines = self.search(
            Domain(domain) & Domain('create_uid', '=', self.env.uid))
        if not lines:
            raise UserError(nothing)
        if len(lines.wizard_id) > 1:
            raise UserError(several)
        return lines

    def action_view_movements(self):
        """Everything that moved through this row, from the button in the list.

        A row of the list is not a cell: it carries receipts and issues side by
        side, so a single click cannot mean one of them and this shows both.
        The list of movements then adds up to no single number of the row, and
        it does not pretend to — it answers "what happened to this material in
        this place", which is the question a row raises.

        A button rather than a click on the row itself: everywhere in Odoo a row
        of a list opens that very record, and a report that quietly means
        something else by it would teach a rule that holds nowhere. This is how
        the standard stock report does it too — the History button on a line of
        the stock on hand (`stock/views/stock_quant_views.xml`).
        """
        # "History" is what the standard stock report calls the same way down,
        # so the word is borrowed rather than invented: a reader meets it in
        # Inventory already.
        return self._movements_action(MOVEMENT_BOTH_ENDS, _('History'))

    def _movements_action(self, ends, name):
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': 'stock.move.line',
            # `views` rather than `view_mode`: this action reaches the client
            # through `call_kw`, and only `call_button` runs it through
            # `clean_action`, which is what turns one into the other
            # (web/controllers/dataset.py). Without the key the client fails on
            # `action.views.map` before anything is shown. `False` for the ids
            # leaves the model's own default views in place.
            'views': [(False, 'list'), (False, 'form')],
            'domain': list(self._move_line_domain(ends)),
            # A movement is recorded by a transfer, never typed into a report.
            'context': {'create': False},
        }

    def _move_line_domain(self, ends):
        """Move lines the report counted into these rows.

        A move line is booked against the place at its own end: it is a receipt
        for the place it went into and an issue for the place it left, so an
        internal transfer appears in both directions with different rows. Which
        end to match on is therefore the whole difference between receipts and
        issues — the row's place and product are the same either way. Naming
        both ends asks for everything that moved through the place.

        The conditions are built per row rather than as three `in` lists: a cell
        can cover several products, places and months at once, and separate
        lists would let combinations through that were never in the report — a
        product from one month together with a place it only sat in in another.

        The bounds are the wizard's own, so the movements are cut exactly where
        the report cut them, the reader's midnight included (see
        `_day_start_utc`); anything else and the list would not add up to the
        number that was clicked. They are written out as strings rather than
        left as `datetime`: this domain travels to the browser inside an action,
        and what a domain looks like there should not depend on what the JSON
        serializer happens to do with a Python object.
        """
        wizard = self.wizard_id
        wizard.ensure_one()
        rows = sorted(
            {(line.product_id, line.location_id, line.date_from, line.date_to)
             for line in self},
            key=lambda row: (row[0].id, row[1].id, row[2], row[3]),
        )
        return Domain.AND([
            Domain([
                ('state', '=', 'done'),
                ('company_id', '=', wizard.company_id.id),
            ]),
            Domain.OR(
                Domain([
                    ('product_id', '=', product.id),
                    ('date', '>=', fields.Datetime.to_string(
                        wizard._day_start_utc(date_from))),
                    ('date', '<', fields.Datetime.to_string(
                        wizard._day_start_utc(date_to, days=1))),
                ]) & Domain.OR(
                    Domain([(end, '=', location.id)]) for end in ends
                )
                for product, location, date_from, date_to in rows
            ),
        ])

    def _collapsed(self, lines):
        """The same rows, folded over the whole period.

        On paper a product must appear once: the form is a summary of a
        period, not its diary. From the list the rows already arrive that way,
        but from the pivot table they are monthly, and printing those would
        repeat the same position with nothing to tell the rows apart (the form
        carries no month column).

        The counterparts are matched by "product + place" pairs rather than by
        two separate `in` conditions: otherwise combinations that were never on
        screen would slip into the form.
        """
        monthly = lines.filtered('is_monthly')
        if not monthly:
            return lines
        pairs = {(line.product_id.id, line.location_id.id) for line in monthly}
        counterparts = self.search(Domain.AND([
            Domain([('wizard_id', 'in', monthly.wizard_id.ids)]),
            Domain([('is_monthly', '=', False)]),
            Domain.OR(
                Domain([('product_id', '=', product), ('location_id', '=', location)])
                for product, location in pairs
            ),
        ]))
        return counterparts | (lines - monthly)

    def _report_signatures(self):
        """Signatures under the form: who handed the report over and who took it.

        The accountant's name comes from the company's `accountant_id` field,
        which l10n_ua_hr_base provides. This module stands on `stock` alone and
        deliberately pulls in neither the HR nor the accounting localization,
        so the field is read softly: with that module installed and a chief
        accountant set the signature is named, without it the line stays empty
        and the name is written in by hand. That way the form prints on any
        database, not only on a fully equipped one.
        """
        company = self.company_id[:1] or self.env.company
        accountant = ''
        if 'accountant_id' in company._fields:
            accountant = company.accountant_id.name or ''
        return [
            # The person in charge hands it over, and their name is already in
            # the header of the form, so only the signature is left here.
            {'title': _('Handed over by'), 'role': '', 'name': ''},
            {'title': _('Accepted by'), 'role': _('Accountant'), 'name': accountant},
        ]

    def _report_category_label(self):
        """Product category for the header of the form.

        Printing starts from an already narrowed report, so when a single
        category is left it characterises the form just as the store or the
        period does, and it is worth naming. When there are several, naming
        one of them would be untrue, and the header says plainly that it is
        all of them.
        """
        categories = self.categ_id
        if len(categories) == 1:
            return categories.complete_name or categories.display_name
        return _('all')

    def _report_totals(self):
        """The total row of the form — over what is actually printed.

        Quantities are not totalled: products are measured in different units.

        Plain sums are right here because the form receives an already
        collapsed set — one row per product and place for the whole period
        (see `_collapsed`). Summing monthly rows this way would not do: the
        closing balance of March plus the closing balance of April means
        nothing.
        """
        return {
            key: sum(self.mapped(key))
            for key in ('opening_value', 'in_value', 'out_value', 'closing_value')
        }
