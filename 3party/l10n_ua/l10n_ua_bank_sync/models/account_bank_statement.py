from odoo import models, fields, api


class AccountBankStatement(models.Model):
    """Native-виписка з метаданими джерела імпорту (Фаза 1 рефактора).

    Виписка формується В ПРОЦЕСІ імпорту як унікальна сутність: несе дату й
    джерело завантаження (файл/API + посилання), а баланси беруться з джерела.
    `l10n_ua_balance_verified` фіксує, чи баланси реально отримані з джерела
    (тоді balance_start + Σ = balance_end — контроль повноти), чи виведені
    постфактум (недостовірний контроль).
    """
    _inherit = 'account.bank.statement'

    l10n_ua_source_type = fields.Selection([
        ('file', 'File import'),
        ('api', 'API'),
        ('manual', 'Manual'),
    ], string='Import Source', help='Тип джерела, з якого сформовано виписку.')
    l10n_ua_source_ref = fields.Char(
        string='Source Reference',
        help='Назва файлу або провайдер/endpoint API.')
    l10n_ua_import_date = fields.Datetime(string='Imported At')
    l10n_ua_sync_job_id = fields.Many2one(
        'l10n_ua.bank.sync.job', string='Sync Job', ondelete='set null')
    l10n_ua_balance_verified = fields.Boolean(
        string='Balance from Source',
        help='Баланси отримані з джерела (контроль повноти дійсний). '
             'Якщо вимкнено — кінцевий баланс виведено з рухів (не перевірка).')
    l10n_ua_balance_ok = fields.Boolean(
        string='Balance Continuity OK', compute='_compute_l10n_ua_balance_ok')

    @api.depends('balance_end', 'balance_end_real', 'l10n_ua_balance_verified')
    def _compute_l10n_ua_balance_ok(self):
        # balance_end (обчислюване) = balance_start + Σ рухів;
        # balance_end_real = закриття з джерела. Контроль повноти: вони рівні.
        for stmt in self:
            stmt.l10n_ua_balance_ok = (
                stmt.l10n_ua_balance_verified
                and abs(stmt.balance_end - stmt.balance_end_real) < 0.01)


class AccountBankStatementLine(models.Model):
    """Рядок native-виписки з зовнішнім ідентифікатором для дедупу імпорту.

    Odoo 19 прибрав `unique_import_id`, тож тримаємо власний індексований
    ключ джерела для ідемпотентного повторного імпорту.
    """
    _inherit = 'account.bank.statement.line'

    l10n_ua_import_uid = fields.Char(
        string='Import UID', index=True,
        help='Зовнішній ідентифікатор руху (для дедупу повторного імпорту).')
