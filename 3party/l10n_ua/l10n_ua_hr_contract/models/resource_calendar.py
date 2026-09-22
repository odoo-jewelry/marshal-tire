from odoo import models, fields


class ResourceCalendar(models.Model):
    """Ukrainian attributes on top of the native working-time calendar.

    Deliberately NOT redefined here: the weekly and daily norms. Odoo 19 core
    already stores both on this model — ``hours_per_week`` and
    ``hours_per_day`` — computing them from the calendar's own attendance
    lines, halving them for a two-week calendar and skipping lunch periods.
    Adding a UA copy would recreate exactly the duplication this change
    removes (#213).

    Only attributes with no core counterpart live here. The ``ua_`` prefix
    keeps them clear of core and of any other module extending
    ``resource.calendar``; note that core already owns a ``schedule_type``
    (flexible / fully fixed), which is a different axis from the Ukrainian
    classification below.
    """

    _inherit = 'resource.calendar'

    ua_code = fields.Char(
        string='Schedule Code',
        index='btree_not_null',
        help='Short code used in reports and imports (STD40, SHIFT2X2).',
    )
    ua_schedule_type = fields.Selection(
        selection=[
            ('standard', 'Standard (5-day week)'),
            ('shift', 'Shift Work'),
            ('flexible', 'Flexible Schedule'),
            ('summarized', 'Summarized Accounting'),
        ],
        string='Schedule Type (UA)',
        default='standard',
        help='Ukrainian classification of the working-time regime. Independent '
             'of the core schedule_type, which only states whether the hours '
             'are fixed or flexible.',
    )

    ua_is_night_work = fields.Boolean(string='Includes Night Work')
    ua_night_start_hour = fields.Float(string='Night Start Hour', default=22.0)
    ua_night_end_hour = fields.Float(string='Night End Hour', default=6.0)
    ua_is_hazardous = fields.Boolean(string='Hazardous Conditions')
    ua_reduced_hours = fields.Boolean(
        string='Reduced Working Hours',
        help='Reduced working time under Article 51 of the Labour Code.',
    )
