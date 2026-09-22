"""Material report — the report a person in charge of a store
files for a period.

The Minstat order No 193 of 21.06.1996, which approved the form, has been
repealed, but the duty to account for the materials held by that person has
not, so this is still the layout Ukrainian accountants ask for.

The figures come from done stock moves in and out of the chosen location, so
the report works on the standard Inventory app alone — no accounting
localization behind it. Amounts are the quantities at the product's cost
price; a report valued from stock valuation layers is a separate job, and this
one deliberately states its basis rather than mixing the two.

Only products with inventory tracking (`is_storable`) are counted: the rest
are costs that merely pass through the store — electricity, wages, overheads —
issued to production and never received back. See `_movement_domain`.

Archived products are left out unless they moved during the period — see
`_moved_products` for why movement, and not the archive date, is what decides.

Rows are per month as well: the period is cut into calendar months, and the
closing balance of one is the opening balance of the next. A one-month period
— the usual one — yields exactly one bucket, so the split shows only on
longer periods, where the point is to see how the store lived month by month
rather than a single lump sum. Beware what that means for aggregation:
receipts and issues are flows and add up across months, balances are a state
and do not.

Rows are per product *and* storage place: the store the report is filed for
is rarely a single shelf, and the person reading it wants to narrow down to
one place. Hence a row is (product, location), where location is the store
itself or any place under it. A move between two places of the same store is
therefore an issue from one and a receipt for the other — that is what makes
each row balance (opening + receipts - issues = closing) and what the storage
place filter is filtering. It also means the total of the receipt and issue
columns counts material that only circulated inside the store; the opening and
closing totals are unaffected, since those transfers cancel out between the
places.

The menu opens the report itself, not a dialog: the current month for the
main store of the company, as a list with category and location search panels
(the shape of the standard Inventory report) or as a pivot table. This model
is what holds the parameters behind those rows, but it has no dialog of its
own: the report is driven from the report. The period is the date range in the
control panel, narrowing is the panel on the left and the search filters, and
the store is the main one of the company.

Printing sits under the cog, and it asks nothing either: the paper form is the
rows already on screen, filters and all, so the two cannot drift apart — the
PDF prints the materialized records rather than recomputing them.
"""

from collections import defaultdict
from datetime import datetime, time, timedelta

import pytz
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class L10nUaMaterialReportWizard(models.TransientModel):
    _name = 'l10n_ua.material.report.wizard'
    _description = 'Material Report'
    # A report is read, not filled in: it stays open on screen for as long as
    # the work takes. The server-wide default (`transient_age_limit`, one hour)
    # is meant for dialogs that are answered and closed, and under it a report
    # left over lunch would be vacuumed away — the period picker would vanish
    # and printing would find no rows. A working day is the honest lifetime
    # here, and raising it on this model alone leaves every other wizard in the
    # database on the default.
    _transient_max_hours = 12

    def _default_location_id(self):
        """The store the report opens on when nobody has chosen one yet.

        This is a report of one person in charge of one store, so a location
        is always needed; the main store of the first warehouse is the one
        an accountant means by default.
        """
        warehouse = self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1)
        return warehouse.lot_stock_id

    date_from = fields.Date(
        string='Period From',
        required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string='Period To',
        required=True,
        default=fields.Date.context_today,
    )
    # `check_company` and the company in the domain go together: the first
    # refuses a store belonging to another company, the second keeps such
    # stores out of the picker in the first place. Locations shared across
    # companies carry no company at all, hence the False in the list.
    location_id = fields.Many2one(
        'stock.location',
        string='Storage Place',
        required=True,
        default=_default_location_id,
        check_company=True,
        domain="[('usage', '=', 'internal'),"
               " ('company_id', 'in', [False, company_id])]",
    )
    # There is nowhere left to type the responsible person: the parameter
    # dialog is gone and the form prints an empty line to sign. The field
    # stays because the form prints it and code can still set it (a default
    # from the context, say).
    responsible_person = fields.Char(
        string='Person in Charge',
        help='The person materially responsible for this store',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    line_ids = fields.One2many(
        'l10n_ua.material.report.line',
        'wizard_id',
        string='Report Lines',
    )
    # What the last print covered. The form is rendered from the wizard rather
    # than from the rows, because Odoo only names the downloaded file after the
    # record when a single one is printed (web/controllers/report.py:134) — and
    # a file called after the store and the period is worth more than one
    # called after the action. The selection cannot travel in the action's
    # `data` either: with `data` set the client builds the URL without docids,
    # and then there is no record to name the file after. So it is kept here.
    #
    # The relation is named explicitly: the two table names joined by Odoo's
    # own rule come to exactly 63 characters, the PostgreSQL limit for an
    # identifier, and nothing should sit that close to a cliff.
    printed_line_ids = fields.Many2many(
        'l10n_ua.material.report.line',
        relation='l10n_ua_material_report_printed_rel',
        column1='wizard_id',
        column2='line_id',
        string='Printed Lines',
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                # ValidationError is the exception a python constraint raises
                # (odoo/exceptions.py); it is a UserError, so the reader sees
                # the same dialog either way.
                raise ValidationError(
                    _('The period must start before it ends.'))

    @api.model
    def action_open_default_report(self):
        """The menu entry: the current month for the main store, no questions.

        Nothing is asked up front and nothing is asked later either: the
        period is changed by the date range in the report's control panel.
        """
        location = self._default_location_id()
        if not location:
            raise UserError(_(
                'Company "%(company)s" has no warehouse, hence no storage '
                'place for the report. Create a warehouse in the Inventory '
                'settings.',
                company=self.env.company.display_name,
            ))
        return self.create({'location_id': location.id}).action_view_report()

    def action_view_report(self):
        """Open the report rows on screen: the list first, the pivot a switch away.

        Which one opens is not a stored parameter — the view switcher of the
        control panel is right there, and a report that reopens on the list is
        what the standard Inventory report does too.
        """
        self.ensure_one()
        self._materialize_lines()

        action = self.env['ir.actions.actions']._for_xml_id(
            'l10n_ua_stock_forms.action_material_report_lines')
        views = [
            (self.env.ref(
                'l10n_ua_stock_forms.view_material_report_line_list').id,
             'list'),
            (self.env.ref(
                'l10n_ua_stock_forms.view_material_report_line_pivot').id,
             'pivot'),
        ]
        action.update({
            'name': _(
                'Material Report (M-19): %(location)s',
                location=self.location_id.display_name,
            ),
            'views': views,
            'view_mode': ','.join(view_type for _view_id, view_type in views),
            # The same narrowing the action record spells out as
            # `[('wizard_id', '=', active_id)]`, written here as a plain list
            # because this path knows the wizard and need not evaluate anything.
            # The record's version is what survives a reload from the URL.
            'domain': [('wizard_id', '=', self.id)],
            'context': {
                # The rows carry no link back to the parameters, so the period
                # picker in the control panel reads the wizard from here.
                #
                # `active_id` rather than a name of our own: it means the record
                # the action was opened from, which is precisely this wizard,
                # and it is the only key the URL carries over a reload. A key of
                # our own would be lost on the way back from a drill-down and
                # the report would come up unnarrowed.
                'active_id': self.id,
                'create': False,
                'edit': False,
            },
        })
        return action

    def action_open_period(self):
        """The dialog behind the period button in the control panel.

        A plain form with the standard `daterange` widget, rather than a
        calendar of our own: two ordinary date fields cannot collapse into a
        single day by a stray click, and the footer of a form is already the
        familiar way to confirm. The button that opens it keeps showing the
        period in force, so the state stays visible without a page of its own.
        """
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Report Period'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'l10n_ua_stock_forms.view_material_report_period_form').id,
                'form')],
            'target': 'new',
        }

    def action_apply_period(self):
        """Rebuild the report for the period the dialog has just written.

        The dates are already on the record — the form saves before calling a
        button — so there is nothing to pass in, and `_check_dates` has judged
        the pair the reader means before we get here. Only the rows are left
        to redo; the view reloads when the dialog closes.
        """
        self.ensure_one()
        self._materialize_lines()
        return {'type': 'ir.actions.act_window_close'}

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def _materialize_lines(self):
        """Store the rows of the report as records the views can query.

        Both granularities at once: the monthly rows feed the pivot table, the
        collapsed ones the list and the printed form. Keeping only one and
        deriving the other on the fly is not an option: the list displays
        records, not something computed on the spot.

        Re-running the report replaces its own rows rather than adding to
        them, so the same wizard can be adjusted and viewed again.
        """
        self.ensure_one()
        self.line_ids.unlink()
        monthly = self._get_report_lines()
        return self.env['l10n_ua.material.report.line'].create(
            [self._prepare_line_values(line, monthly=True) for line in monthly]
            + [self._prepare_line_values(line) for line in self._collapse_lines(monthly)]
        )

    def _collapse_lines(self, lines):
        """Monthly rows folded into one per product and storage place.

        Receipts and issues add up, the opening balance comes from the first
        month and the closing one from the last. Balances must not be added:
        they are a state at a moment, not a flow.

        The rows arrive already ordered by month (`_get_report_lines`), so the
        first and the last fall out of the iteration order itself.
        """
        self.ensure_one()
        collapsed = {}
        for line in lines:
            key = (line['product'], line['location'])
            row = collapsed.get(key)
            if row is None:
                collapsed[key] = dict(line, date_from=self.date_from,
                                      date_to=self.date_to)
                continue
            for key_qty in ('in_qty', 'in_value', 'out_qty', 'out_value'):
                row[key_qty] += line[key_qty]
            for key_closing in ('closing_qty', 'closing_value'):
                row[key_closing] = line[key_closing]
        return list(collapsed.values())

    def _prepare_line_values(self, line, monthly=False):
        self.ensure_one()
        product = line['product']
        values = {
            'is_monthly': monthly,
            'wizard_id': self.id,
            'product_id': product.id,
            'default_code': line['code'],
            'categ_id': product.categ_id.id,
            'uom_id': product.uom_id.id,
            'location_id': line['location'].id,
            'date_from': line['date_from'],
            'date_to': line['date_to'],
            'company_id': self.company_id.id,
            'currency_id': self.company_id.currency_id.id,
        }
        values.update({
            key: line[key] for key in (
                'price',
                'opening_qty', 'opening_value',
                'in_qty', 'in_value',
                'out_qty', 'out_value',
                'closing_qty', 'closing_value',
            )
        })
        return values

    def _timezone(self):
        """The zone the picked dates are meant in — the reader's own.

        A period is picked as calendar days, and a day only exists in some
        zone. Move lines, meanwhile, are stored in UTC, so the two have to be
        brought together somewhere; here is that place.
        """
        return pytz.timezone(
            self.env.context.get('tz') or self.env.user.tz or 'UTC')

    def _day_start_utc(self, day, days=0):
        """Midnight of a local day as the naive UTC the database stores."""
        local = self._timezone().localize(
            datetime.combine(day + timedelta(days=days), time.min))
        return local.astimezone(pytz.utc).replace(tzinfo=None)

    def _movement_domain(self, date_from, date_to, end):
        """Done move lines whose `end` is inside the store.

        `end` says which side of the move is being asked about:
        `location_dest_id` for what came in, `location_id` for what went out. A
        move line is booked against the place at its own end, so a transfer
        between two places of the store answers both questions — as an issue of
        the place it left and as a receipt of the place it reached. Netting it
        out instead would leave the balance of neither place adding up.

        Products with inventory tracking only (`is_storable`). The rest are
        costs passing through the store in transit: electricity, wages,
        overheads. They are issued to production and never received back,
        because they hold no balance at all, and in the report they used to produce
        a permanently negative one — not an arithmetic slip, but an attempt to
        count what the store does not hold.

        Both ends of the period are inclusive, and both are the reader's days
        rather than UTC ones. That distinction is not pedantry: with the zone
        ignored, a report for July in Kyiv (UTC+3) would actually run from
        03:00 on 1 July to 02:59 on 1 August, quietly dropping the first hours
        of the first day and taking in the first hours of August instead.

        The upper bound is the start of the day *after* `date_to`, taken as
        `<`: that admits the whole last day down to the microsecond, whereas
        `<= 23:59:59` would silently lose the final second of it.
        """
        self.ensure_one()
        domain = [
            ('state', '=', 'done'),
            ('company_id', '=', self.company_id.id),
            ('product_id.is_storable', '=', True),
            (end, 'child_of', self.location_id.id),
        ]
        if date_from:
            domain.append(('date', '>=', self._day_start_utc(date_from)))
        if date_to:
            domain.append(('date', '<', self._day_start_utc(date_to, days=1)))
        return domain

    def _movements(self, date_from, date_to):
        """{(product, location): {'in': qty, 'out': qty}} in the product's unit.

        The database does the adding up. It matters most where it is least
        visible: the opening balance asks for every movement of the store since
        it began, and turning each of them into a record only to add a number to
        a total is what would eventually make the report too slow to open. Here
        Python sees one row per product and place instead of one per movement.

        Two groupings rather than one, because a move line answers for two
        places at once — see `_movement_domain` for which end means what.

        The quantity is `quantity_product_uom`, which stock stores already
        converted into the product's own unit
        (`_compute_quantity_product_uom`, stock/models/stock_move_line.py:168).
        Converting line by line here would repeat work already done — and would
        have to happen before summing, which is precisely what would rule out a
        database sum.
        """
        self.ensure_one()
        MoveLine = self.env['stock.move.line']
        movements = defaultdict(lambda: {'in': 0.0, 'out': 0.0})
        for direction, end in (('in', 'location_dest_id'),
                               ('out', 'location_id')):
            groups = MoveLine._read_group(
                self._movement_domain(date_from, date_to, end),
                groupby=['product_id', end],
                aggregates=['quantity_product_uom:sum'],
            )
            for product, location, quantity in groups:
                movements[(product, location)][direction] += quantity
        return movements

    def _moved_products(self, during):
        """Products that actually moved during the period.

        The criterion is a forced one. Archived products are unwanted in the
        report, yet the ones that were in use during this very period must not
        be lost either. It cannot be decided exactly: `active` on
        product.template and product.product is declared without tracking, so
        the database holds no archiving history — the flag does not say when a
        product was archived, nor whether it was active for even a day of the
        period.

        Movement is therefore taken as the sign of "was in use": a product
        handled that month can only have been archived later. This has exactly
        one blind spot — a product that stayed active all period, sat without
        movement and was archived afterwards will vanish from old reports.
        Only tracking the `active` field can remove it, and then only from the
        day tracking is switched on.
        """
        return {
            product
            for movements in during.values()
            for (product, _location), qty in movements.items()
            if qty['in'] or qty['out']
        }

    def _period_months(self):
        """Months of the period as (first day, row start, row end).

        The edge months are clipped to the period bounds: for 15.03–20.05 the
        March row starts on 15.03 and the May one ends on 20.05. That way the
        receipts summed over months equal the receipts of the period, no more.
        """
        self.ensure_one()
        months = []
        month_start = self.date_from.replace(day=1)
        while month_start <= self.date_to:
            next_month = month_start + relativedelta(months=1)
            months.append((
                month_start,
                max(month_start, self.date_from),
                min(next_month - relativedelta(days=1), self.date_to),
            ))
            month_start = next_month
        return months

    def _get_report_lines(self):
        """Rows of the report table: one per product, storage place and month.

        The month is the finest unit of the report, because a month is what
        the person in charge reports for. A typical one-month period yields a
        single bucket, that is the same rows as before; the split only tells
        on longer periods, where otherwise one would see the totals alone
        rather than how the store lived month by month.

        The balance carries over from month to month: the end of March is the
        beginning of April. That is why the months are walked in order instead
        of being computed each on its own.

        Each month is asked for separately, with its own bounds in the domain.
        Grouping by month in SQL would work too, but the bounds are the
        reader's midnights (`_day_start_utc`), and stating them in the domain
        keeps that rule in one place instead of splitting it between our code
        and the timezone the database happens to group by. A period is a
        handful of months, so it is a handful of grouped queries.
        """
        self.ensure_one()
        # Cost prices are company-dependent (`standard_price` on
        # product.product), and this report names its own company. Read in the
        # environment's company instead, a report of one company would quietly
        # be valued at the prices of another.
        self = self.with_company(self.company_id)

        months = self._period_months()
        before = self._movements(
            False, fields.Date.subtract(self.date_from, days=1))
        during = {
            month_start: self._movements(row_from, row_to)
            for month_start, row_from, row_to in months
        }

        empty = {'in': 0.0, 'out': 0.0}
        places = set(before).union(*during.values())
        moved_products = self._moved_products(during)

        lines = []
        for product, location in places:
            # An archived product with no movement in the period is a balance
            # dragged in from older times; it does not enter the report. See
            # `_moved_products` on why movement is the criterion.
            if not product.active and product not in moved_products:
                continue
            opened = before.get((product, location), empty)
            balance = opened['in'] - opened['out']
            price = product.standard_price or 0.0
            for month_start, date_from, date_to in months:
                moved = during[month_start].get((product, location), empty)
                opening = balance
                received = moved['in']
                issued = moved['out']
                closing = opening + received - issued
                balance = closing
                # A product that neither moved during the month nor holds a
                # balance stays off the form — otherwise the report grows over
                # with zeros.
                if not any((opening, received, issued, closing)):
                    continue
                lines.append({
                    'product': product,
                    'location': location,
                    # `place` and `name` are read by the sort below and by
                    # nothing else: the stored row takes its place and its name
                    # from `location_id` and `product_id`.
                    'place': location.complete_name,
                    'code': product.default_code or '',
                    'name': product.display_name,
                    'date_from': date_from,
                    'date_to': date_to,
                    'price': price,
                    'opening_qty': opening,
                    'opening_value': opening * price,
                    'in_qty': received,
                    'in_value': received * price,
                    'out_qty': issued,
                    'out_value': issued * price,
                    'closing_qty': closing,
                    'closing_value': closing * price,
                })
        return sorted(
            lines,
            key=lambda line: (line['name'], line['place'], line['date_from']))
