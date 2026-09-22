"""Тести проведення місячної амортизації в Головну книгу — issue #136.

Дт рахунок витрат (23/91/92/93/94) — Кт 131 «Знос ОЗ».
"""

from datetime import date
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestDepreciationPosting(TransactionCase):
    """Проводки амортизації ОЗ."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.journal = cls.env['account.journal'].search([
            ('type', '=', 'general'),
            ('company_id', '=', cls.company.id),
        ], limit=1) or cls.env['account.journal'].create({
            'name': 'Тестовий загальний',
            'code': 'TGENA',
            'type': 'general',
            'company_id': cls.company.id,
        })

        Account = cls.env['account.account']

        def _acc(code, name, account_type):
            acc = Account.search([
                ('code', '=', code),
                ('company_ids', 'in', cls.company.id),
            ], limit=1)
            if not acc:
                acc = Account.create({
                    'code': code,
                    'name': name,
                    'account_type': account_type,
                    'company_ids': [(4, cls.company.id)],
                })
            return acc

        cls.acc_expense = _acc('9231', 'Загальновиробничі витрати', 'expense')
        cls.acc_accum = _acc('1312', 'Знос ОЗ', 'asset_fixed')

        cls.group = cls.env['l10n_ua.asset.group'].create({
            'code': 'DEP',
            'name': 'Група з рахунками амортизації',
            'min_useful_life': 5,
            'depreciation_journal_id': cls.journal.id,
            'expense_account_id': cls.acc_expense.id,
            'depreciation_account_id': cls.acc_accum.id,
        })

    def _create_asset(self, group=True, **kwargs):
        vals = {
            'name': 'ОЗ для амортизації',
            'acquisition_date': date(2025, 1, 15),
            'commission_date': date(2025, 1, 15),
            'original_value': 60000,
            'salvage_value': 0,
            'depreciation_method': 'straight_line',
            'useful_life': 60,  # 1000/міс
            'company_id': self.company.id,
        }
        if group:
            vals['group_id'] = self.group.id
        vals.update(kwargs)
        return self.env['l10n_ua.asset'].create(vals)

    def _first_draft_line(self, asset):
        asset.action_compute_depreciation()
        return asset.depreciation_line_ids.filtered(
            lambda l: l.state == 'draft' and l.line_type == 'depreciation')[:1]

    def test_post_creates_balanced_move(self):
        """Проведення рядка формує збалансовану проводку Дт витрати / Кт 131."""
        asset = self._create_asset()
        line = self._first_draft_line(asset)
        self.assertTrue(line)
        line.action_post()

        self.assertEqual(line.state, 'posted')
        move = line.move_id
        self.assertTrue(move, 'Має бути створено account.move')
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.date, line.date)
        self.assertEqual(move.journal_id, self.journal)

        debit_line = move.line_ids.filtered(lambda l: l.account_id == self.acc_expense)
        credit_line = move.line_ids.filtered(lambda l: l.account_id == self.acc_accum)
        self.assertAlmostEqual(debit_line.debit, line.amount, places=2)
        self.assertAlmostEqual(credit_line.credit, line.amount, places=2)
        self.assertAlmostEqual(sum(move.line_ids.mapped('debit')),
                               sum(move.line_ids.mapped('credit')), places=2)

    def test_draft_removes_move(self):
        """Скасування проведення видаляє проводку."""
        asset = self._create_asset()
        line = self._first_draft_line(asset)
        line.action_post()
        move = line.move_id
        self.assertTrue(move.exists())

        line.action_draft()
        self.assertEqual(line.state, 'draft')
        self.assertFalse(line.move_id)
        self.assertFalse(move.exists())

    def test_asset_override_wins_over_group(self):
        """Рахунки, вказані на ОЗ, мають пріоритет над груповими."""
        other_expense = self.env['account.account'].create({
            'code': '9232', 'name': 'Інші витрати', 'account_type': 'expense',
            'company_ids': [(4, self.company.id)],
        })
        asset = self._create_asset(expense_account_id=other_expense.id)
        line = self._first_draft_line(asset)
        line.action_post()
        debit_line = line.move_id.line_ids.filtered(lambda l: l.debit > 0)
        self.assertEqual(debit_line.account_id, other_expense)

    def test_missing_accounts_raise(self):
        """Без налаштованих рахунків проведення неможливе."""
        asset = self._create_asset(group=False)
        line = self._first_draft_line(asset)
        with self.assertRaises(UserError):
            line.action_post()
        self.assertEqual(line.state, 'draft')
