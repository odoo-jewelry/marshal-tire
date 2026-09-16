{
    "name": "POS Historical Stock Write-off",
    "version": "19.0.2.0.0",
    "category": "Point of Sale",
    "summary": "Record historical stock consumption and manually recompute subsequent costs",
    "license": "LGPL-3",
    "depends": ["pos_order_correction", "pos_cost_recompute", "stock_account", "product_card_consolidation"],
    "data": [
        "security/historical_security.xml",
        "views/historical_views.xml",
        "views/recompute_views.xml",
        "views/consolidation_views.xml",
    ],
    "installable": True,
}
