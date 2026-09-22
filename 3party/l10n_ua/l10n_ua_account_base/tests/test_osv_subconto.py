"""Тести ОСВ по субконто (#144).

Покриття:
- Розбивка ОСВ за видом субконто (партнер) — сальдо/обороти на значення субконто
- Фільтр за одним рахунком
- Валідація: тип «subconto» без обраного виду субконто
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestOsvSubconto(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.subconto_partner = cls.env.ref(
            'l10n_ua_account_base.subconto_type_partner')
        cls.p1 = cls.env['res.partner'].create({'name': 'Субконто П1'})
        cls.p2 = cls.env['res.partner'].create({'name': 'Субконто П2'})
        cls.journal = cls.env['account.journal'].create({
            'name': 'ОСВ-суб тест', 'code': 'OSVS',
            'type': 'general', 'company_id': cls.company.id})
        cls.acc_a = cls.env['account.account'].create({
            'name': 'Суб актив', 'code': 'OSVSA',
            'account_type': 'asset_current',
            'company_ids': [(4, cls.company.id)]})
        cls.acc_b = cls.env['account.account'].create({
            'name': 'Суб дохід', 'code': 'OSVSB',
            'account_type': 'income',
            'company_ids': [(4, cls.company.id)]})

    def _move(self, move_date, amount, subconto_partner):
        """Проводка Дт acc_a (із субконто-партнером) / Кт acc_b."""
        move = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': self.journal.id,
            'date': move_date,
            'line_ids': [
                (0, 0, {'account_id': self.acc_a.id, 'debit': amount, 'credit': 0.0}),
                (0, 0, {'account_id': self.acc_b.id, 'debit': 0.0, 'credit': amount}),
            ],
        })
        line_a = move.line_ids.filtered(lambda l: l.account_id == self.acc_a)
        line_a.subconto_partner_id = subconto_partner
        move.action_post()
        return move

    def _osv(self):
        return self.env['l10n_ua.osv'].create({
            'period_start': date(2025, 1, 1),
            'period_end': date(2025, 12, 31),
            'osv_type': 'subconto',
            'subconto_type_id': self.subconto_partner.id,
            'account_id': self.acc_a.id,
            'company_id': self.company.id,
        })

    def test_subconto_breakdown(self):
        self._move(date(2024, 12, 31), 500.0, self.p1)  # opening П1
        self._move(date(2025, 3, 1), 100.0, self.p1)     # turnover П1
        self._move(date(2025, 4, 1), 60.0, self.p2)      # turnover П2

        osv = self._osv()
        osv.action_compute()

        # Дві лінії — по значенню субконто (П1, П2).
        self.assertEqual(len(osv.line_ids), 2)
        line_p1 = osv.line_ids.filtered(
            lambda l: l.subconto_label == self.p1.display_name)
        line_p2 = osv.line_ids.filtered(
            lambda l: l.subconto_label == self.p2.display_name)
        self.assertEqual(len(line_p1), 1)
        self.assertEqual(len(line_p2), 1)

        self.assertAlmostEqual(line_p1.opening_debit, 500.0)
        self.assertAlmostEqual(line_p1.turnover_debit, 100.0)
        self.assertAlmostEqual(line_p1.closing_debit, 600.0)
        self.assertAlmostEqual(line_p2.turnover_debit, 60.0)
        self.assertAlmostEqual(line_p2.closing_debit, 60.0)

    def test_account_filter(self):
        """account_id обмежує ОСВ одним рахунком."""
        self._move(date(2025, 5, 1), 200.0, self.p1)
        osv = self._osv()  # account_id = acc_a
        osv.action_compute()
        # Жодного рядка acc_b (кредит-сторона) — лише acc_a.
        self.assertTrue(all(l.account_id == self.acc_a for l in osv.line_ids))

    def test_subconto_requires_type(self):
        osv = self.env['l10n_ua.osv'].create({
            'period_start': date(2025, 1, 1),
            'period_end': date(2025, 12, 31),
            'osv_type': 'subconto',
            'company_id': self.company.id,
        })
        with self.assertRaises(UserError):
            osv.action_compute()
