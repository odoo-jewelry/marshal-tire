# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    chatter_toggle_enabled = fields.Boolean(
        string="Chatter Toggle Button",
        config_parameter="web_chatter_toggle.enabled",
        help="Show a chatter show/hide toggle button on every form view, "
             "like the one in the To-do app.",
    )
