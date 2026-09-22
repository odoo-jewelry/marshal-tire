from odoo import api, fields, models


class L10nUaFopGroup(models.Model):
    _name = 'l10n_ua.fop.group'
    _description = 'Група платника єдиного податку'
    _order = 'code'

    code = fields.Selection(
        selection=[
            ('1', '1 група'),
            ('2', '2 група'),
            ('3', '3 група (без ПДВ)'),
            ('3_vat', '3 група (з ПДВ)'),
        ],
        string='Група',
        required=True,
    )
    name = fields.Char(
        string='Назва',
        required=True,
        translate=True,
    )
    tax_rate = fields.Float(
        string='Ставка ЄП (%)',
        help='Ставка єдиного податку як відсоток від доходу',
    )
    limit_min_wages = fields.Integer(
        string='Ліміт доходу, мінімальних зарплат',
        help='Граничний річний дохід групи в розмірах мінімальної заробітної плати, '
             'установленої на 1 січня року (п. 291.4 ПКУ): 167 / 834 / 1167.',
    )
    income_limit = fields.Monetary(
        string='Ліміт річного доходу (поточний рік)',
        compute='_compute_income_limit',
        currency_field='currency_id',
    )
    can_hire_employees = fields.Boolean(
        string='Може наймати працівників',
    )
    max_employees = fields.Integer(
        string='Макс. кількість працівників',
    )
    description = fields.Text(
        string='Опис',
        translate=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
    )
    active = fields.Boolean(
        default=True,
    )

    @api.depends('limit_min_wages')
    def _compute_income_limit(self):
        year = fields.Date.context_today(self).year
        for group in self:
            group.income_limit = group._get_income_limit(year)

    def _get_income_limit(self, year):
        """Граничний дохід групи за рік; 0.0, якщо мінзарплату на рік не задано."""
        self.ensure_one()
        min_wage = self.env['l10n_ua.min.wage']._get_amount(f'{year}-01-01')
        return self.limit_min_wages * min_wage
