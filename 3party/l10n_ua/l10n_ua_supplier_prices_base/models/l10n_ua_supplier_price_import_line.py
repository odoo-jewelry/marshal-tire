from odoo import api, fields, models, _


class L10nUaSupplierPriceImportLine(models.Model):
    _name = 'l10n_ua.supplier.price.import.line'
    _description = 'Supplier Price Import Line'
    _order = 'import_id, sequence, id'

    import_id = fields.Many2one(
        'l10n_ua.supplier.price.import',
        string='Import',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    supplier_sku = fields.Char(string='Supplier SKU', required=True, index=True)
    supplier_name = fields.Char(string='Supplier Product Name')
    barcode = fields.Char(string='Barcode')
    description = fields.Text(string='Description')
    price = fields.Float(string='Price', digits=(16, 4))
    currency_id = fields.Many2one('res.currency', string='Currency')
    qty_min = fields.Float(string='Min Qty', default=1.0)
    uom_text = fields.Char(string='UoM (text)', help='Текстове представлення з файлу')
    date_valid = fields.Date(string='Valid From')

    product_id = fields.Many2one(
        'product.product',
        string='Matched Product',
        help='Знайдено за supplier_sku в product.supplierinfo',
    )
    product_supplierinfo_id = fields.Many2one(
        'product.supplierinfo',
        string='Supplierinfo',
        help='Створений/оновлений запис після apply',
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('matched', 'Matched'),
            ('unknown', 'Unknown SKU'),
            ('created', 'Product Created'),
            ('skipped', 'Skipped'),
            ('error', 'Error'),
        ],
        default='pending',
        required=True,
    )
    error_message = fields.Char(string='Error', readonly=True)

    @api.constrains('price')
    def _check_price(self):
        for line in self:
            if line.price < 0:
                raise models.ValidationError(_("Price cannot be negative on line for SKU %s.") % line.supplier_sku)

    def _find_product(self):
        """Знайти product.product за supplier_sku в product.supplierinfo."""
        self.ensure_one()
        partner = self.import_id.partner_id
        if not partner:
            return False
        domain = [
            ('partner_id', '=', partner.id),
            ('product_code', '=', self.supplier_sku),
        ]
        info = self.env['product.supplierinfo'].search(domain, limit=1)
        return info.product_id or info.product_tmpl_id.product_variant_id or False

    def _apply_to_supplierinfo(self):
        """Створити або оновити product.supplierinfo для цього рядка."""
        self.ensure_one()
        source = self.import_id.source_id
        partner = self.import_id.partner_id

        if not partner:
            self.write({'status': 'error', 'error_message': _('Source has no supplier configured.')})
            return

        product = self._find_product()
        if not product:
            self._handle_unknown_sku()
            if self.status in ('skipped', 'error', 'unknown'):
                return

        currency = self.currency_id or source.currency_default_id
        vals = {
            'partner_id': partner.id,
            'product_code': self.supplier_sku,
            'product_name': self.supplier_name or False,
            'price': self.price,
            'currency_id': currency.id if currency else False,
            'min_qty': self.qty_min,
            'company_id': source.company_id.id if source.company_id else False,
        }
        if self.date_valid:
            vals['date_start'] = self.date_valid

        existing_domain = [
            ('partner_id', '=', partner.id),
            ('product_code', '=', self.supplier_sku),
        ]
        if source.company_id:
            existing_domain.append(('company_id', '=', source.company_id.id))
        else:
            existing_domain.append(('company_id', '=', False))

        existing = self.env['product.supplierinfo'].search(existing_domain, limit=1)
        if existing:
            existing.write(vals)
            info = existing
        else:
            if product:
                vals['product_id'] = product.id
                vals['product_tmpl_id'] = product.product_tmpl_id.id
            info = self.env['product.supplierinfo'].create(vals)

        self.write({
            'product_id': product.id if product else False,
            'product_supplierinfo_id': info.id,
            'status': 'matched' if product else self.status,
        })

    def _handle_unknown_sku(self):
        """Виконати дію згідно source.unknown_sku_action."""
        self.ensure_one()
        action = self.import_id.source_id.unknown_sku_action
        if action == 'skip':
            self.status = 'skipped'
        elif action == 'log_only':
            self.status = 'unknown'
        elif action == 'error_stop':
            self.write({'status': 'error', 'error_message': _('Unknown SKU.')})
            raise models.ValidationError(_(
                "Unknown SKU '%(sku)s' on line, and source is configured to stop on unknown.",
                sku=self.supplier_sku,
            ))
        elif action == 'create_product':
            product = self.env['product.product'].create({
                'name': self.supplier_name or self.supplier_sku,
                'default_code': self.supplier_sku,
                'barcode': self.barcode or False,
                'type': 'consu',
                'purchase_ok': True,
            })
            self.write({'product_id': product.id, 'status': 'created'})
