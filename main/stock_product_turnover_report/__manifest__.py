{
    "name": "Product Stock Turnover Report",
    "version": "19.0.1.2.0",
    "category": "Inventory/Reporting",
    "summary": "Read-only product stock turnover and valuation statement",
    "author": "Uvelirsoft",
    "depends": ["stock_account"],
    "data": ["views/product_stock_turnover_views.xml"],
    "assets": {
        "web.assets_backend": [
            "stock_product_turnover_report/static/src/stock_product_turnover/product_stock_turnover.js",
            "stock_product_turnover_report/static/src/stock_product_turnover/product_stock_turnover.xml",
            "stock_product_turnover_report/static/src/stock_product_turnover/product_stock_turnover.scss",
        ],
    },
    "installable": True,
    "license": "LGPL-3",
}
