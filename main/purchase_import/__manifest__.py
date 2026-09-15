{
    "name": "Purchase Order Line Import",
    "version": "19.0.1.0.0",
    "category": "Purchases",
    "summary": "Import purchase order lines from CSV and XLSX files",
    'author': 'dmitry.aka.jok@gmail.com',
    "website": "https://uvelirsoft.com.ua",
    "depends": [
        "base_import",
        "purchase",
        "stock",
    ],
    "data": [
        "security/purchase_import_security.xml",
        "security/ir.model.access.csv",
        "views/import_profile_views.xml",
        "views/purchase_order_views.xml",
        "wizard/purchase_order_line_import_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "OPL-1",
}
