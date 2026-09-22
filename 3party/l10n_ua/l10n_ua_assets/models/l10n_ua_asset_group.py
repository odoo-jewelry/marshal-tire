from odoo import fields, models


class L10nUaAssetGroup(models.Model):
    _name = 'l10n_ua.asset.group'
    _description = 'Fixed Asset Group (Tax Code)'
    _order = 'code'

    code = fields.Char(
        string='Code',
        required=True,
    )
    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    min_useful_life = fields.Integer(
        string='Min Useful Life (years)',
        help='Minimum useful life according to Tax Code',
    )
    description = fields.Text(
        string='Description',
        translate=True,
    )

    # --- Default accounts for monthly depreciation posting ---
    depreciation_journal_id = fields.Many2one(
        'account.journal',
        string='Журнал амортизації',
        domain="[('type', '=', 'general')]",
        help='Журнал за замовчуванням для проводок місячної амортизації',
    )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Рахунок витрат (Дт)',
        help='Рахунок витрат на амортизацію за замовч. (23/91/92/93/94)',
    )
    depreciation_account_id = fields.Many2one(
        'account.account',
        string='Рахунок зносу (Кт 131)',
        help='Рахунок накопиченого зносу за замовч. (131)',
    )

    active = fields.Boolean(
        default=True,
    )

    _unique_code = models.Constraint(
        'UNIQUE(code)',
        'Asset group code must be unique!',
    )
