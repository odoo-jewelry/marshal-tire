"""Донесення класу 0 до компаній, які вже працюють на плані `ua_psbo`.

Шаблон плану рахунків матеріалізується один раз — коли на компанію ставиться
локалізація. Для баз, де `l10n_ua` встановили раніше за цей модуль (тобто для
всіх наявних), самого `@template` замало: нові рахунки просто нікуди не
потраплять. Тому після встановлення проходимо по компаніях і створюємо те,
чого бракує.

Ідемпотентно: рахунок з таким кодом у компанії створюється лише якщо його ще
немає, тож повторне оновлення модуля нічого не дублює.

`post_init_hook` спрацьовує тільки при встановленні модуля (`loading.py`,
`update_operation == 'install'`). Для баз, де модуль уже стоїть, те саме
викликає `migrations/19.0.1.1.0/post-migration.py` — без нього саме ті
компанії, заради яких цей файл написано, класу 0 так і не отримали б.
"""
import logging

from .models.template_ua_psbo import OFFBALANCE_ACCOUNTS

_logger = logging.getLogger(__name__)


def ensure_offbalance_accounts(env):
    """Створити відсутні рахунки класу 0 всім компаніям на плані `ua_psbo`."""
    Account = env['account.account']
    # Коди в плані доповнюються нулями до code_digits (для ua_psbo це 6), тож
    # рахунок 01 має стати 010000 — інакше хук наплодив би дублікати поруч із
    # тими, що прийшли шаблоном. Полегшений `_get_chart_template_model_data`
    # тут не годиться: для 'template_data' функції повертають плаский словник
    # значень, а не xmlid → значення, і він на ньому падає.
    digits = int(env['account.chart.template']._get_chart_template_data('ua_psbo')
                 ['template_data'].get('code_digits') or 6)

    companies = env['res.company'].search([('chart_template', '=', 'ua_psbo')])
    for company in companies:
        wanted = {code.ljust(digits, '0'): (name, analytics)
                  for code, name, analytics in OFFBALANCE_ACCOUNTS}
        existing = set(Account.with_company(company).search([
            ('code', 'in', list(wanted)),
            ('company_ids', 'parent_of', company.id),
        ]).mapped('code'))
        missing = {code: vals for code, vals in wanted.items() if code not in existing}
        if not missing:
            continue
        Account.with_company(company).create([{
            'code': code,
            'name': name,
            'account_type': 'off_balance',
            'reconcile': False,
            'ua_analytics_type': analytics,
            'company_ids': [(6, 0, [company.id])],
        } for code, (name, analytics) in missing.items()])
        _logger.info('l10n_ua_account_base: додано %s позабалансових рахунків для %s',
                     len(missing), company.display_name)


def post_init_hook(env):
    ensure_offbalance_accounts(env)
