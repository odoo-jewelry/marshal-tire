{
    "name": "Product Card Consolidation",
    "version": "19.0.2.0.0",
    "category": "Inventory/Products",
    "summary": "Safely consolidate duplicate single-variant product cards",
    'author': 'dmitry.aka.jok@gmail.com',
    "website": "https://uvelirsoft.com.ua",
    "depends": [
        "purchase_import",
        "sale_management",
        "stock_account",
    ],
    "data": [
        "security/product_card_consolidation_security.xml",
        "security/ir.model.access.csv",
        "wizard/product_consolidation_wizard_views.xml",
        "views/product_template_views.xml",
        "views/stock_move_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "OPL-1",
}
