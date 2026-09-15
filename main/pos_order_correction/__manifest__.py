{
    "name": "POS Order Correction",
    "version": "19.0.1.0.0",
    "category": "Point of Sale",
    "summary": "Correct completed POS orders through auditable revisions",
    "author": "Uvelirsoft",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "pos_customer_debt"],
    "data": [
        "security/pos_order_correction_security.xml",
        "security/ir.model.access.csv",
        "views/pos_order_correction_views.xml",
        "views/pos_order_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "pos_order_correction/static/src/ticket_screen.js",
            "pos_order_correction/static/src/ticket_screen.xml",
        ],
    },
    "installable": True,
}
