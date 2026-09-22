from odoo import fields, models


class L10nUaSupplierPriceMappingField(models.Model):
    _name = 'l10n_ua.supplier.price.mapping.field'
    _description = 'Supplier Price Mapping Field'
    _order = 'sequence, id'

    mapping_id = fields.Many2one(
        'l10n_ua.supplier.price.mapping',
        string='Mapping',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    target = fields.Selection(
        selection=[
            ('sku', 'Supplier SKU'),
            ('name', 'Product Name'),
            ('price', 'Price'),
            ('currency', 'Currency Code'),
            ('qty_min', 'Minimum Quantity'),
            ('uom', 'Unit of Measure'),
            ('date_valid', 'Valid From'),
            ('barcode', 'Barcode'),
            ('description', 'Description'),
        ],
        required=True,
        string='Target Field',
    )
    source_path = fields.Char(
        string='Source Path',
        required=True,
        help='Парсер-специфічний шлях:\n'
             'JSON: items[*].price.value\n'
             'XML: //product/price/text()\n'
             'CSV/XLSX: column name або index',
    )
    required = fields.Boolean(default=True)
    default_value = fields.Char(
        string='Default Value',
        help='Використовується якщо source_path не знайдено і поле required=False',
    )
    transform = fields.Selection(
        selection=[
            ('none', 'No transform'),
            ('strip', 'Trim whitespace'),
            ('upper', 'UPPERCASE'),
            ('lower', 'lowercase'),
            ('to_float', 'String → float'),
            ('to_decimal', 'String → Decimal (для цін)'),
            ('parse_date', 'Parse date'),
            ('multiply', 'Multiply by N'),
            ('replace_comma', 'Replace , with . (для чисел)'),
        ],
        default='none',
    )
    transform_param = fields.Char(
        string='Transform Parameter',
        help='Параметр для transform: формат для parse_date, число для multiply',
    )
