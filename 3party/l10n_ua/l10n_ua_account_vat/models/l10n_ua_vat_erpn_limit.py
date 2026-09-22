from odoo import api, fields, models, _
from odoo.exceptions import UserError


class L10nUaVatErpnLimit(models.Model):
    _name = 'l10n_ua.vat.erpn.limit'
    _description = 'ERPN Registration Limit (Реєстраційний ліміт)'
    _order = 'date desc'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Назва',
        compute='_compute_name',
        store=True,
    )
    date = fields.Date(
        string='Дата розрахунку',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Компанія',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
    )

    # Formula components: Ліміт = ΣПодЗоб + ΣМитноПДВ + ΣБюджВідшк + ΣОтримПДВ − ΣВиданПДВ − ΣВідшкод
    amount_overpayment = fields.Monetary(
        string='Переплата (ΣПодЗоб)',
        currency_field='currency_id',
        tracking=True,
        help='Сума податкового зобов\'язання — сплачено більше, ніж нараховано',
    )
    amount_import_vat = fields.Monetary(
        string='ПДВ з імпорту (ΣМитноПДВ)',
        currency_field='currency_id',
        tracking=True,
        help='Сума ПДВ, сплаченого при розмитненні',
    )
    amount_budget_refund = fields.Monetary(
        string='Бюджетне відшкодування (ΣБюджВідшк)',
        currency_field='currency_id',
        tracking=True,
        help='Сума бюджетного відшкодування',
    )
    amount_received_vat = fields.Monetary(
        string='Отриманий ПДВ (ΣОтримПДВ)',
        currency_field='currency_id',
        tracking=True,
        help='Сума ПДВ з отриманих податкових накладних',
    )
    amount_issued_vat = fields.Monetary(
        string='Виданий ПДВ (ΣВиданПДВ)',
        currency_field='currency_id',
        tracking=True,
        help='Сума ПДВ з виданих податкових накладних',
    )
    amount_refunded = fields.Monetary(
        string='Відшкодовано (ΣВідшкод)',
        currency_field='currency_id',
        tracking=True,
        help='Сума вже отриманого бюджетного відшкодування',
    )
    limit_amount = fields.Monetary(
        string='Реєстраційний ліміт',
        compute='_compute_limit_amount',
        store=True,
        currency_field='currency_id',
    )
    notes = fields.Text(
        string='Примітки',
    )

    @api.depends('date', 'company_id')
    def _compute_name(self):
        for rec in self:
            if rec.date:
                rec.name = _('Ліміт ЄРПН на %s') % rec.date
            else:
                rec.name = _('Новий розрахунок ліміту')

    @api.depends(
        'amount_overpayment', 'amount_import_vat', 'amount_budget_refund',
        'amount_received_vat', 'amount_issued_vat', 'amount_refunded',
    )
    def _compute_limit_amount(self):
        for rec in self:
            rec.limit_amount = (
                rec.amount_overpayment
                + rec.amount_import_vat
                + rec.amount_budget_refund
                + rec.amount_received_vat
                - rec.amount_issued_vat
                - rec.amount_refunded
            )

    def action_calculate_from_registers(self):
        """Pre-fill received/issued VAT from confirmed registers."""
        self.ensure_one()
        Register = self.env['l10n_ua.vat.register']

        # Get all confirmed registers
        issued_regs = Register.search([
            ('register_type', '=', 'issued'),
            ('state', '=', 'confirmed'),
            ('company_id', '=', self.company_id.id),
        ])
        received_regs = Register.search([
            ('register_type', '=', 'received'),
            ('state', '=', 'confirmed'),
            ('company_id', '=', self.company_id.id),
        ])

        self.write({
            'amount_issued_vat': sum(issued_regs.mapped('total_vat')),
            'amount_received_vat': sum(received_regs.mapped('total_vat')),
        })
