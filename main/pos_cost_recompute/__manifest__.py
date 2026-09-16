{
    "name": "POS Cost Recompute",
    "version": "19.0.1.1.2",
    "category": "Point of Sale",
    "summary": "Review and recompute historical POS costs using standard sources",
    "author": "Uvelirsoft",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "stock_account"],
    "data": [
        "security/ir.model.access.csv",
        "security/pos_cost_recompute_security.xml",
        "views/pos_cost_recompute_views.xml",
        "views/pos_order_views.xml",
    ],
    "installable": True,
}
