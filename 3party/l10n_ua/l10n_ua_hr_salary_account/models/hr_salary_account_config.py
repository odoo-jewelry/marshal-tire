import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrSalaryAccountConfig(models.Model):
    _name = 'hr.salary.account.config'
    _description = 'Salary Account Configuration'
    _rec_name = 'company_id'

    company_id = fields.Many2one(
        'res.company',
        string='Компанія',
        required=True,
        default=lambda self: self.env.company,
    )

    # --- Journal ---
    salary_journal_id = fields.Many2one(
        'account.journal',
        string='Журнал зарплати',
        domain="[('type', '=', 'general'), ('company_id', '=', company_id)]",
        help='Журнал для проводок по зарплаті (тип: загальний)',
    )

    # --- Liability accounts (credit side) ---
    wages_payable_account_id = fields.Many2one(
        'account.account',
        string='661 — Розрахунки за ЗП',
        help='Рахунок 661 — Розрахунки за заробітною платою',
    )
    pdfo_payable_account_id = fields.Many2one(
        'account.account',
        string='6411 — ПДФО',
        help='Рахунок 6411 — Розрахунки за ПДФО',
    )
    military_tax_payable_account_id = fields.Many2one(
        'account.account',
        string='6415 — Військовий збір',
        help='Рахунок 6415 — Розрахунки за військовим збором',
    )
    esv_payable_account_id = fields.Many2one(
        'account.account',
        string='651 — ЄСВ',
        help='Рахунок 651 — Розрахунки за ЄСВ',
    )
    other_payable_account_id = fields.Many2one(
        'account.account',
        string='685 — Інші кредитори',
        help='Рахунок 685 — Розрахунки з іншими кредиторами (аліменти, профспілка тощо)',
    )

    # --- Default expense account (debit side) ---
    default_expense_account_id = fields.Many2one(
        'account.account',
        string='Рахунок витрат за замовчуванням',
        help='Рахунок витрат за замовчуванням (92 — Адміністративні витрати). '
             'Використовується, якщо у підрозділу не вказано окремий рахунок.',
    )

    # --- Options ---
    entry_granularity = fields.Selection(
        [
            ('per_batch', 'Зведена проводка (одна на пачку)'),
            ('per_payslip', 'Окрема проводка на кожен розрахунковий листок'),
        ],
        string='Деталізація проводок',
        default='per_batch',
        required=True,
        help='Зведена проводка — одна проводка на місяць (рекомендовано). '
             'Окрема — по проводці на кожного працівника.',
    )
    auto_post = fields.Boolean(
        string='Автоматично проводити',
        default=False,
        help='Автоматично проводити (підтверджувати) створені проводки',
    )

    _company_uniq = models.Constraint(
        'unique(company_id)',
        'Для кожної компанії може бути лише одна конфігурація рахунків зарплати!',
    )

    @api.model
    def get_config(self, company=None):
        """Get salary account config for the given company."""
        company = company or self.env.company
        config = self.search([('company_id', '=', company.id)], limit=1)
        if not config:
            raise UserError(
                'Не знайдено налаштування рахунків зарплати для компанії "%s". '
                'Перейдіть у Зарплата → Налаштування → Рахунки зарплати '
                'та створіть конфігурацію.' % company.name
            )
        return config

    def _validate_accounts(self):
        """Check that required accounts are configured."""
        self.ensure_one()
        missing = []
        if not self.salary_journal_id:
            missing.append('Журнал зарплати')
        if not self.wages_payable_account_id:
            missing.append('661 — Розрахунки за ЗП')
        if not self.pdfo_payable_account_id:
            missing.append('6411 — ПДФО')
        if not self.military_tax_payable_account_id:
            missing.append('6415 — Військовий збір')
        if not self.esv_payable_account_id:
            missing.append('651 — ЄСВ')
        if not self.default_expense_account_id:
            missing.append('Рахунок витрат за замовчуванням')
        if missing:
            raise UserError(
                'Не заповнено обов\'язкові рахунки в налаштуваннях зарплати:\n- '
                + '\n- '.join(missing)
            )
