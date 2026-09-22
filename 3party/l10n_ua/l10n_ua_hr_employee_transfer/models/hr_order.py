from odoo import models, fields


class HrOrder(models.Model):
    _inherit = 'hr.order'

    personnel_form = fields.Selection(
        [
            ('p1', 'П-1 (прийняття)'),
            ('p4', 'П-4 (звільнення)'),
            ('p7', 'П-7 (переведення)'),
        ],
        string='Типова кадрова форма',
        help='Позначка типової кадрової форми (наказ переведення — П-7).',
    )
    new_version_id = fields.Many2one(
        'hr.version', string='Створена версія контракту',
        help='Версія трудового договору, створена цим наказом (переведення).',
    )
