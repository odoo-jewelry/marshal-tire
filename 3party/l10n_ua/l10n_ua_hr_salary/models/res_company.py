from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    payroll_bank_account_id = fields.Many2one(
        'res.partner.bank', string='Payroll Payer Account',
        help='Рахунок компанії-платника для зарплатного банк-файлу.')
    payroll_bank_file_format = fields.Selection(
        [('xml', 'XML'), ('dbf', 'DBF'),
         ('ifobs', 'iFOBS (Укргазбанк та ін.)'),
         ('ibank2', 'iBank 2 UA (VST Bank та ін.)')],
        string='Payroll Bank File Format', default='xml',
        help='Типовий формат зарплатного файлу для клієнт-банку.')
    payroll_payment_purpose = fields.Char(
        string='Payroll Payment Purpose',
        default='Заробітна плата за {period}',
        help='Шаблон призначення платежу. Плейсхолдери: {period}, '
             '{employee}, {rnokpp}.')
    # Реквізити зарплатного проєкту клієнт-банку (iFOBS / iBank 2 UA)
    payroll_transit_account_id = fields.Many2one(
        'res.partner.bank', string='Payroll Transit Account',
        help='Транзитний рахунок зарплатного проєкту (iFOBS TRACCIBAN).')
    payroll_salary_project_code = fields.Char(
        string='Salary Project Code (ЗКП)',
        help='Код зарплатного проєкту (iFOBS CODEZKP).')
    payroll_accrual_name = fields.Char(
        string='Payroll Accrual Type',
        default='Заробітна плата',
        help='Найменування виду нарахування (iFOBS FLOWTYPE / iBank 2 UA '
             'ONFLOW_TYPE) з довідника банку.')
