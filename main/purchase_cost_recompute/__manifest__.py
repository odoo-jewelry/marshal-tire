{
    "name": "Purchase Cost Recompute",
    "version": "19.0.1.4.0",
    "category": "Purchases",
    "summary": "Include purchase taxes in prices and recompute historical costs",
    "author": "Uvelirsoft",
    "license": "LGPL-3",
    "depends": ["purchase_stock", "pos_cost_recompute"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/purchase_cost_recompute_views.xml",
        "views/purchase_order_views.xml",
    ],
    "installable": True,
}
