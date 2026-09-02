# -*- coding: utf-8 -*-
from odoo import models
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        enabled = (
            request.env["ir.config_parameter"]
            .sudo()
            .get_param("web_chatter_toggle.enabled")
        )
        info["web_chatter_toggle_enabled"] = enabled == "True"
        return info
