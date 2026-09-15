{
    'name': 'Tire',
    'version': '19.0.1.3.0',
    'category': 'Sales',
    'summary': 'Tire management',
    'author': 'dmitry.aka.jok@gmail.com',
    'website': 'https://uvelirsoft.com.ua',
    'depends': [
        'point_of_sale',
        'pos_cost_recompute',
        'product',
        'stock',
        'sale_management',
        'purchase',
        'purchase_import',
        'purchase_price_control',
        'product_card_consolidation',

        'disable_odoo_online',
        'portal_debranding',
        'remove_odoo_enterprise',
        'web_dialog_size',
        'web_remember_tree_column_width',
        
        'web_chatter_toggle'

    ],
    'data': [
        'views/product_template_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'tire/static/src/app/product_card/product_screen.xml',
            'tire/static/src/app/product_card/product_card.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
