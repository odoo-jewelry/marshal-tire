from odoo import api, fields, models


class L10nUaMinWage(models.Model):
    """Мінімальна заробітна плата за датою початку дії.

    Розмір встановлює закон про Державний бюджет на кожен рік, іноді з
    підвищенням посеред року. Від неї рахуються мінімальний ЄСВ і ліміти
    доходу платників єдиного податку (п. 291.4 ПКУ — на 1 січня року).
    На новий рік достатньо додати запис, а не правити константи в коді.
    """
    _name = 'l10n_ua.min.wage'
    _description = 'Мінімальна заробітна плата'
    _order = 'date_from desc'

    date_from = fields.Date(
        string='Діє з',
        required=True,
        index=True,
    )
    amount = fields.Float(
        string='Місячний розмір, грн',
        required=True,
        digits=(16, 2),
    )
    legal_basis = fields.Char(
        string='Підстава',
        help='Закон, яким установлено розмір',
    )

    _date_from_uniq = models.Constraint(
        'UNIQUE(date_from)',
        'Мінімальну заробітну плату на цю дату вже задано!',
    )
    _amount_positive = models.Constraint(
        'CHECK(amount > 0)',
        'Мінімальна заробітна плата має бути більшою за нуль!',
    )

    @api.depends('date_from', 'amount')
    def _compute_display_name(self):
        for rec in self:
            if rec.date_from:
                rec.display_name = f'{rec.amount:,.2f} грн з {rec.date_from:%d.%m.%Y}'
            else:
                rec.display_name = f'{rec.amount:,.2f} грн'

    @api.model
    def _get_amount(self, on_date):
        """Мінімальна зарплата, чинна на дату, або 0.0, якщо її не задано.

        Шукаємо лише серед записів того самого року: розмір щороку
        встановлює новий закон, тож сума минулого року для нового року —
        це відсутні дані, а не чинне значення.
        """
        on_date = fields.Date.to_date(on_date)
        record = self.sudo().search([
            ('date_from', '<=', on_date),
            ('date_from', '>=', on_date.replace(month=1, day=1)),
        ], order='date_from desc', limit=1)
        return record.amount if record else 0.0
