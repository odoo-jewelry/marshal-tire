from . import models


def post_init_hook(env):
    """Give the UA schedules to the companies that already exist on install.

    New companies get their own set through res.company.create(); this hook
    covers the ones created earlier.
    """
    env['res.company'].search([])._l10n_ua_create_resource_calendars()
