{
    "name": "Purchase Price Control",
    "version": "19.0.4.1.0",
    "category": "Purchases",
    "summary": "Control reference purchase prices and sales markup from purchase orders",
    'author': 'dmitry.aka.jok@gmail.com',
    "website": "https://uvelirsoft.com.ua",
    "depends": [
        "purchase",
        "purchase_stock",
        "stock_account",
    ],
    "data": [
        "views/purchase_order_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "OPL-1",
}
