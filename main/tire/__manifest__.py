{
    'name': 'Tire',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Tire management',
    'author': 'dmitry.aka.jok@gmail.com',
    'website': 'https://uvelirsoft.com.ua',
    'depends': [
        'point_of_sale',
        'product',
        'stock',
    ],
    'data': [
        'views/product_template_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'tire/static/src/app/product_card/product_card.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'OPL-1',
}
