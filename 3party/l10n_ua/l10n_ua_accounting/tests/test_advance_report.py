"""Tests for advance-report posting (авансовий звіт) — issue #188.

Covers:
- action_post creates a balanced journal entry (Дт витрати — Кт 372)
- 372 settlement account resolved by code when company field is unset
- move_id linked, state -> posted
- guards: no lines, zero total, missing expense account, double posting
"""

from odoo.exceptions import UserError
from odoo.tests import tagged
from .common import AccountingTestCase


@tagged('post_install', '-at_install')
class TestAdvanceReport(AccountingTestCase):
    """Test advance-report journal-entry creation on posting."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Account = cls.env['account.account']
        # Accountable-persons settlement account (372) — credited on posting.
        # Reuse the chart's 372 if present so `_get_settlement_account`'s
        # by-code lookup resolves to the SAME account this test references
        # (a freshly-created "3721" would be shadowed by the chart's "372").
        cls.account_372 = Account.search([('code', '=like', '372%')], limit=1)
        if not cls.account_372:
            cls.account_372 = Account.create({
                'code': '3721',
                'name': 'Розрахунки з підзвітними особами (тест)',
                'account_type': 'asset_current',
                'company_ids': [(6, 0, [cls.company.id])],
            })
        # Expense account (Дт)
        cls.account_92 = Account.create({
            'code': '9201',
            'name': 'Адміністративні витрати (тест)',
            'account_type': 'expense',
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.company.l10n_ua_advance_journal_id = cls.misc_journal

    def _new_report(self, amount=1500.0, account=None, **kw):
        vals = {
            'employee_id': self.employee.id,
            'purpose': 'Відрядження',
            'advance_amount': 2000.0,
            'line_ids': [(0, 0, {
                'description': 'Таксі',
                'expense_type': 'transport',
                'amount': amount,
                'account_id': (account or self.account_92).id,
            })],
        }
        vals.update(kw)
        return self.env['l10n_ua.advance.report'].create(vals)

    def _to_approved(self, report):
        report.action_submit()
        report.action_approve()

    def test_post_creates_balanced_move(self):
        """Posting creates a posted, balanced Дт витрати / Кт 372 entry."""
        report = self._new_report(amount=1500.0)
        self.assertEqual(report.total_expenses, 1500.0)
        self._to_approved(report)
        report.action_post()

        self.assertEqual(report.state, 'posted')
        self.assertTrue(report.move_id, 'move_id must be linked')
        move = report.move_id
        self.assertEqual(move.state, 'posted')
        self.assertEqual(move.journal_id, self.misc_journal)

        debit = move.line_ids.filtered(lambda l: l.account_id == self.account_92)
        credit = move.line_ids.filtered(lambda l: l.account_id == self.account_372)
        self.assertEqual(debit.debit, 1500.0)
        self.assertEqual(credit.credit, 1500.0)
        self.assertEqual(sum(move.line_ids.mapped('debit')),
                         sum(move.line_ids.mapped('credit')))

    def test_settlement_account_resolved_by_code(self):
        """With no company 372 field, account is found by code 372%."""
        self.company.l10n_ua_advance_account_id = False
        report = self._new_report()
        self._to_approved(report)
        report.action_post()
        credit = report.move_id.line_ids.filtered(lambda l: l.credit)
        self.assertEqual(credit.account_id, self.account_372)

    def test_default_expense_account_used_when_line_empty(self):
        """Line without account falls back to the company default expense account."""
        self.company.l10n_ua_advance_expense_account_id = self.account_92
        report = self.env['l10n_ua.advance.report'].create({
            'employee_id': self.employee.id,
            'purpose': 'Купівля канцтоварів',
            'line_ids': [(0, 0, {
                'description': 'Папір',
                'expense_type': 'supplies',
                'amount': 300.0,
            })],
        })
        self._to_approved(report)
        report.action_post()
        debit = report.move_id.line_ids.filtered(lambda l: l.debit)
        self.assertEqual(debit.account_id, self.account_92)

    def test_missing_expense_account_raises(self):
        """No line account and no company default -> clear error."""
        self.company.l10n_ua_advance_expense_account_id = False
        report = self.env['l10n_ua.advance.report'].create({
            'employee_id': self.employee.id,
            'purpose': 'Інше',
            'line_ids': [(0, 0, {
                'description': 'Без рахунку',
                'expense_type': 'other',
                'amount': 100.0,
            })],
        })
        self._to_approved(report)
        with self.assertRaises(UserError):
            report.action_post()

    def test_cannot_post_without_lines(self):
        """A report with no expense lines cannot be posted."""
        report = self.env['l10n_ua.advance.report'].create({
            'employee_id': self.employee.id,
            'purpose': 'Порожній',
        })
        # submit is also blocked without lines; approve state reached manually
        report.state = 'approved'
        with self.assertRaises(UserError):
            report.action_post()

    def test_double_post_blocked(self):
        """Re-posting an already posted report is rejected."""
        report = self._new_report()
        self._to_approved(report)
        report.action_post()
        report.state = 'approved'  # force state back without clearing move
        with self.assertRaises(UserError):
            report.action_post()
