from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nUaSupplierPriceMapping(models.Model):
    _name = 'l10n_ua.supplier.price.mapping'
    _description = 'Supplier Price Mapping Configuration'
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    record_path = fields.Char(
        string='Record Path',
        help='Шлях до масиву записів у файлі. '
             'Поля у field_ids — відносно цього шляху.\n'
             'JSON: items, products, data.list\n'
             'XML: //product, /catalog/items/item\n'
             'CSV/XLSX: залишити порожнім (рядки = записи)',
    )
    parser_config = fields.Text(
        string='Parser Config',
        help='JSON з parser-specific налаштуваннями. Формат залежить від parser_type.\n'
             'CSV: {"delimiter": ";", "encoding": "windows-1251", "has_header": true, "skip_rows": 0}\n'
             'XLSX: {"sheet_name": "Sheet1", "header_row": 1}\n'
             'XML: {"namespaces": {"ns": "http://..."}}',
    )
    field_ids = fields.One2many(
        'l10n_ua.supplier.price.mapping.field',
        'mapping_id',
        string='Mapping Fields',
    )
    source_count = fields.Integer(
        string='Used by Sources',
        compute='_compute_source_count',
    )

    def _compute_source_count(self):
        Source = self.env['l10n_ua.supplier.price.source']
        for mapping in self:
            mapping.source_count = Source.search_count([('mapping_id', '=', mapping.id)])

    @api.constrains('field_ids')
    def _check_required_targets(self):
        required_targets = {'sku', 'price'}
        for mapping in self:
            present = {f.target for f in mapping.field_ids}
            missing = required_targets - present
            if missing:
                raise ValidationError(_(
                    "Mapping '%(name)s' must define fields for: %(missing)s",
                    name=mapping.name,
                    missing=', '.join(sorted(missing)),
                ))
