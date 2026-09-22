"""Wizard for printing Ukrainian Inventory Act (Інвентаризаційний опис, форма ІНВ-3)."""

from odoo import models, fields, api


class L10nUaInventoryActWizard(models.TransientModel):
    _name = 'l10n_ua.inventory.act.wizard'
    _description = 'Інвентаризаційний опис (ІНВ-3)'

    date = fields.Date(
        string='Дата інвентаризації',
        required=True,
        default=fields.Date.context_today,
    )
    location_id = fields.Many2one(
        'stock.location',
        string='Місце зберігання',
        required=True,
        domain="[('usage', '=', 'internal')]",
    )
    order_number = fields.Char(
        string='№ наказу',
        help='Номер наказу про проведення інвентаризації',
    )
    order_date = fields.Date(
        string='Дата наказу',
    )
    commission_head = fields.Char(
        string='Голова комісії',
    )
    commission_members = fields.Text(
        string='Члени комісії',
        help='По одному на рядок',
    )
    responsible_person = fields.Char(
        string='МВО (відповідальна особа)',
        help='Матеріально відповідальна особа',
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
    )
    include_zero = fields.Boolean(
        string='Включити нульові залишки',
        default=False,
    )

    def action_print(self):
        """Generate and print the inventory act."""
        self.ensure_one()
        return self.env.ref(
            'l10n_ua_accounting.action_report_inventory_act'
        ).report_action(self)

    def _get_inventory_lines(self):
        """Get quant data for the report."""
        self.ensure_one()
        domain = [
            ('location_id', 'child_of', self.location_id.id),
        ]
        if not self.include_zero:
            domain.append(('quantity', '!=', 0))

        quants = self.env['stock.quant'].search(
            domain, order='product_id, lot_id'
        )

        lines = []
        idx = 0
        for quant in quants:
            idx += 1
            product = quant.product_id
            lines.append({
                'num': idx,
                'product_name': product.display_name,
                'product_code': product.default_code or '',
                'uom': product.uom_id.name,
                'accounting_qty': quant.quantity,
                'actual_qty': (
                    quant.inventory_quantity
                    if quant.inventory_quantity_set
                    else quant.quantity
                ),
                'difference': (
                    quant.inventory_diff_quantity
                    if quant.inventory_quantity_set
                    else 0
                ),
                'lot': quant.lot_id.name if quant.lot_id else '',
                'location': quant.location_id.complete_name,
            })
        return lines
