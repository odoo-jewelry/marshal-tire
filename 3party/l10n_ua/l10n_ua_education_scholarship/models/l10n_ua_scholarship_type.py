from odoo import api, fields, models


SCHOLARSHIP_INSTITUTION_TYPE = [
    ('professional', 'Професійна освіта'),
    ('pre_higher', 'Фахова передвища освіта'),
    ('higher', 'Вища освіта'),
]

COMPANY_INSTITUTION_MAP = {
    'pto': 'professional',
    'zvo_1_2': 'pre_higher',
    'zvo_3_4': 'higher',
}


class L10nUaScholarshipType(models.Model):
    """Тип стипендії.

    Розміри встановлює Постанова КМУ № 1047 від 28.12.2016.
    Порядок стипендіального забезпечення затверджено Постановою КМУ № 1050.
    """
    _name = 'l10n_ua.scholarship.type'
    _description = 'Тип стипендії'
    _order = 'sequence, code'

    name = fields.Char(string='Назва', required=True, translate=True)
    code = fields.Char(string='Код', required=True, index=True)
    sequence = fields.Integer(default=10)
    kind = fields.Selection([
        ('academic', 'Академічна'),
        ('social', 'Соціальна'),
        ('presidential', 'Президентська'),
        ('rada', 'Верховної Ради'),
        ('regional', 'Обласна / місцева'),
        ('named', 'Іменна'),
        ('other', 'Інша'),
    ], string='Категорія', required=True, default='academic')
    monthly_amount = fields.Monetary(
        string='Місячна сума за замовчуванням',
        currency_field='currency_id',
        help='Резервний базовий розмір, якщо для типу закладу та періоду немає '
             'датованої ставки. Можна перевизначити на рівні рядка виплати.')
    currency_id = fields.Many2one(
        'res.currency', string='Валюта',
        default=lambda self: self.env.company.currency_id)
    default_kekv_id = fields.Many2one(
        'l10n_ua.kekv', string='КЕКВ за замовчуванням',
        domain="[('child_ids', '=', False)]",
        help='Зазвичай КЕКВ 2720 «Стипендії»')
    is_taxable_pdfo = fields.Boolean(
        string='Оподатковується ПДФО',
        help='Чи підлягає стипендія оподаткуванню податком на доходи фізосіб '
             '(зазвичай стипендії в межах прожиткового мінімуму не оподатковуються).')
    description = fields.Html(string='Опис / нормативне обґрунтування')
    rate_ids = fields.One2many(
        'l10n_ua.scholarship.rate', 'scholarship_type_id',
        string='Розміри за періодами')
    active = fields.Boolean(default=True)

    def _get_monthly_amount(self, effective_date, company=None):
        """Return the rate effective for a company institution on a date."""
        self.ensure_one()
        company = company or self.env.company
        institution_type = COMPANY_INSTITUTION_MAP.get(
            company.l10n_ua_education_type)
        if institution_type and effective_date:
            rate = self.env['l10n_ua.scholarship.rate'].search([
                ('scholarship_type_id', '=', self.id),
                ('institution_type', '=', institution_type),
                ('date_from', '<=', effective_date),
            ], order='date_from desc', limit=1)
            if rate:
                return rate.amount
        return self.monthly_amount

    _code_uniq = models.Constraint(
        'unique(code)',
        'Код типу стипендії має бути унікальним!',
    )


class L10nUaScholarshipRate(models.Model):
    """A statutory monthly scholarship amount effective from a date."""
    _name = 'l10n_ua.scholarship.rate'
    _description = 'Розмір стипендії за періодом'
    _order = 'date_from desc, institution_type'

    scholarship_type_id = fields.Many2one(
        'l10n_ua.scholarship.type', string='Тип стипендії', required=True,
        ondelete='cascade', index=True)
    institution_type = fields.Selection(
        SCHOLARSHIP_INSTITUTION_TYPE, string='Рівень освіти', required=True,
        index=True)
    date_from = fields.Date(string='Чинна з', required=True, index=True)
    amount = fields.Monetary(
        string='Місячна сума', required=True,
        currency_field='currency_id')
    currency_id = fields.Many2one(
        related='scholarship_type_id.currency_id', store=True, readonly=True)
    legal_basis = fields.Char(string='Нормативна підстава')

    _type_institution_date_uniq = models.Constraint(
        'unique(scholarship_type_id, institution_type, date_from)',
        'Для типу стипендії, рівня освіти й дати може бути лише одна ставка!',
    )
    _amount_positive = models.Constraint(
        'check(amount > 0)',
        'Розмір стипендії має бути більшим за нуль!',
    )
