from odoo import api, fields, models


class L10nUaMedecinSpecialty(models.Model):
    """Медична спеціалізація / профіль.

    Реєстр професій лікарів за наказом МОЗ + специфічні профілі для НСЗУ-пакетів.
    """
    _name = 'l10n_ua.medecin.specialty'
    _description = 'Медична спеціалізація'
    _order = 'sequence, code'

    code = fields.Char(string='Код', required=True, index=True)
    name = fields.Char(string='Назва', required=True, translate=True)
    sequence = fields.Integer(default=10)
    category = fields.Selection([
        ('primary', 'Первинна (ПМД)'),
        ('specialized', 'Спеціалізована'),
        ('emergency', 'Екстрена'),
        ('dental', 'Стоматологічна'),
        ('rehab', 'Реабілітація'),
        ('lab', 'Лабораторна'),
        ('other', 'Інша'),
    ], string='Категорія', default='specialized')
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        'unique(code)',
        'Код спеціалізації має бути унікальним!',
    )
