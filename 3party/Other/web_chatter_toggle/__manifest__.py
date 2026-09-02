# -*- coding: utf-8 -*-
{
    "name": "Chatter Toggle Everywhere",
    "version": "19.0.2.0.7",
    "summary": "To-do style chatter show/hide toggle button on every form view",
    "description": "Adds a chatter toggle button on all form views so users can "
                   "hide the chatter panel and work full width. Can be enabled "
                   "or disabled from General Settings.",
    "category": "Productivity",
    "author": "MM Solutions",
    "website": "https://apps.odoo.com/apps/modules/browse?author=MM%20Solutions",
    "support": "midhunmmkmr@gmail.com",
    "license": "LGPL-3",
    "depends": ["web", "mail", "base_setup"],
    "data": [
        "data/ir_config_parameter_data.xml",
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "web_chatter_toggle/static/src/chatter_toggle.js",
            "web_chatter_toggle/static/src/chatter_toggle.xml",
            "web_chatter_toggle/static/src/chatter_toggle.scss",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
}
