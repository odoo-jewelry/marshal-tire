{
    "name": "Dynamic Stock Turnover Report",
    "version": "19.0.1.0.0",
    "category": "Inventory/Reporting",
    "summary": "Stock turnover by spatial dimensions and FIFO receipts",
    "author": "Uvelirsoft",
    "depends": [
        "dynamic_accounts_report",
        "stock_account",
        "purchase_stock",
        "sale_stock",
        "point_of_sale",
    ],
    "data": ["views/stock_dynamic_turnover_views.xml"],
    "assets": {
        "web.assets_backend": [
            "stock_dynamic_turnover_report/static/src/stock_dynamic_turnover/stock_dynamic_turnover.js",
            "stock_dynamic_turnover_report/static/src/stock_dynamic_turnover/stock_dynamic_turnover.xml",
            "stock_dynamic_turnover_report/static/src/stock_dynamic_turnover/stock_dynamic_turnover.scss",
        ],
    },
    "installable": True,
    "license": "LGPL-3",
}
