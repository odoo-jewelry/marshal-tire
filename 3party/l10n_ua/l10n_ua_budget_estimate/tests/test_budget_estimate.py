"""Tests for l10n_ua_budget_estimate — estimate document, lines, plan vs actual."""
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_budget_estimate')
class TestBudgetEstimate(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.kekv_2111 = cls.env.ref('l10n_ua_budget_base.kekv_2111')
        cls.kekv_2273 = cls.env.ref('l10n_ua_budget_base.kekv_2273')
        cls.kpkvk = cls.env.ref('l10n_ua_budget_base.kpkvk_2201190_2025')

    def _make_estimate(self, **kwargs):
        defaults = {
            'title': 'Тест-кошторис',
            'year': 2025,
            'fund_type': 'both',
            'kpkvk_id': self.kpkvk.id,
        }
        defaults.update(kwargs)
        return self.env['l10n_ua.budget.estimate'].create(defaults)

    def _make_line(self, estimate, kekv, fund='general', m01=0, m06=0, m12=0):
        return self.env['l10n_ua.budget.estimate.line'].create({
            'estimate_id': estimate.id,
            'kekv_id': kekv.id,
            'fund_type': fund,
            'm01': m01, 'm06': m06, 'm12': m12,
        })

    def test_create_and_sequence(self):
        est = self._make_estimate()
        self.assertNotEqual(est.name, 'Новий')
        self.assertTrue(est.name.startswith('КШ-'),
                         f"expected sequence prefix КШ-, got {est.name!r}")
        self.assertEqual(est.state, 'draft')

    def test_period_dates_autofill(self):
        est = self._make_estimate(year=2024)
        self.assertEqual(str(est.date_from), '2024-01-01')
        self.assertEqual(str(est.date_to), '2024-12-31')

    def test_quarter_and_annual_compute(self):
        est = self._make_estimate()
        line = self._make_line(est, self.kekv_2111, m01=100, m06=200, m12=300)
        # only m01, m06, m12 are set
        self.assertEqual(line.q1, 100)
        self.assertEqual(line.q2, 200)
        self.assertEqual(line.q3, 0)
        self.assertEqual(line.q4, 300)
        self.assertEqual(line.amount_planned, 600)

    def test_state_machine_happy_path(self):
        est = self._make_estimate()
        self._make_line(est, self.kekv_2111, m01=1000)
        # draft -> submit
        est.action_submit()
        self.assertEqual(est.state, 'submitted')
        # submitted -> approve (sets approval metadata)
        est.action_approve()
        self.assertEqual(est.state, 'approved')
        self.assertTrue(est.approval_date)
        self.assertEqual(est.approved_by_id, self.env.user)
        # approved -> execute -> close
        est.action_execute()
        self.assertEqual(est.state, 'executed')
        est.action_close()
        self.assertEqual(est.state, 'closed')

    def test_cannot_submit_empty_estimate(self):
        est = self._make_estimate()
        with self.assertRaises(UserError):
            est.action_submit()

    def test_cannot_skip_states(self):
        est = self._make_estimate()
        self._make_line(est, self.kekv_2111, m01=10)
        # draft -> approve directly: not allowed
        with self.assertRaises(UserError):
            est.action_approve()

    def test_cannot_cancel_closed(self):
        est = self._make_estimate()
        self._make_line(est, self.kekv_2111, m01=10)
        est.action_submit()
        est.action_approve()
        est.action_close()
        with self.assertRaises(UserError):
            est.action_cancel()

    def test_fund_mismatch_with_header(self):
        est = self._make_estimate(fund_type='general')
        with self.assertRaises(ValidationError):
            self._make_line(est, self.kekv_2111, fund='special', m01=10)

    def test_totals_split_by_fund(self):
        est = self._make_estimate()
        self._make_line(est, self.kekv_2111, fund='general', m01=1000)
        self._make_line(est, self.kekv_2273, fund='special', m01=500)
        self.assertEqual(est.total_general, 1000)
        self.assertEqual(est.total_special, 500)
        self.assertEqual(est.total_planned, 1500)

    def test_year_validation(self):
        with self.assertRaises(ValidationError):
            self._make_estimate(year=1800)

    def test_negative_monthly_rejected(self):
        est = self._make_estimate()
        with self.assertRaises(ValidationError):
            self._make_line(est, self.kekv_2111, m01=-100)

    def test_plan_vs_actual_aggregation(self):
        """A posted journal entry with matching analytics should bump amount_actual."""
        est = self._make_estimate()
        line = self._make_line(est, self.kekv_2111, fund='general', m01=10_000)
        self.assertEqual(line.amount_actual, 0)

        # Create matching journal lines via a posted entry
        Move = self.env['account.move']
        # Pick two existing accounts for a balanced entry
        expense_acct = self.env['account.account'].search(
            [('account_type', '=', 'expense'),
             ('company_ids', 'parent_of', self.company.id)], limit=1)
        liab_acct = self.env['account.account'].search(
            [('account_type', '=', 'liability_current'),
             ('company_ids', 'parent_of', self.company.id)], limit=1)
        self.assertTrue(expense_acct, 'No expense account available for test')
        self.assertTrue(liab_acct, 'No liability_current account available for test')

        move = Move.create({
            'move_type': 'entry',
            'date': '2025-06-15',
            'company_id': self.company.id,
            'line_ids': [
                (0, 0, {
                    'account_id': expense_acct.id,
                    'name': 'salary draft',
                    'debit': 3000.0, 'credit': 0,
                    'ua_kekv_id': self.kekv_2111.id,
                    'ua_fund_type': 'general',
                }),
                (0, 0, {
                    'account_id': liab_acct.id,
                    'name': 'payable',
                    'debit': 0, 'credit': 3000.0,
                    'ua_kekv_id': self.kekv_2111.id,
                    'ua_fund_type': 'general',
                }),
            ],
        })
        move.action_post()

        # Force recompute (depends on stored fields not re-triggered by entry post)
        line._compute_amount_actual()
        self.assertEqual(line.amount_actual, 3000.0)
        self.assertEqual(line.variance, 7000.0)
        self.assertAlmostEqual(line.execution_percent, 30.0, places=2)
