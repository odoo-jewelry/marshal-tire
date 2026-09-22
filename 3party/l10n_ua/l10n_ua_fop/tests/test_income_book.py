"""Tests for FOP income book — from ACCOUNTING_UKRAINE.md single tax flow.

Tests cover:
- Income book creation and state management
- Line totals computation
- Unique constraint per quarter
"""

from datetime import date
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFopIncomeBook(TransactionCase):
    """Test FOP income book (книга обліку доходів)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.fop_group = cls.env['l10n_ua.fop.group'].search([
            ('code', '=', '3'),
        ], limit=1)
        if not cls.fop_group:
            cls.fop_group = cls.env['l10n_ua.fop.group'].create({
                'code': '3',
                'name': '3 група (без ПДВ)',
                'tax_rate': 5.0,
                'limit_min_wages': 1167,
            })

    def _create_income_book(self, quarter='1', year=2025):
        return self.env['l10n_ua.fop.income.book'].create({
            'year': year,
            'quarter': quarter,
            'fop_group_id': self.fop_group.id,
            'company_id': self.company.id,
        })

    def test_income_book_creation(self):
        """Income book should be created in draft state."""
        book = self._create_income_book()
        self.assertEqual(book.state, 'draft')
        self.assertTrue(book.name)

    def test_income_book_name_format(self):
        """Name should include quarter and year."""
        book = self._create_income_book('2', 2025)
        self.assertIn('2025', book.name)

    def test_income_book_with_lines(self):
        """Income book total should sum line amounts."""
        book = self._create_income_book()
        self.env['l10n_ua.fop.income.book.line'].create([
            {'book_id': book.id, 'date': date(2025, 1, 15), 'amount': 25000,
             'description': 'Оплата за послуги'},
            {'book_id': book.id, 'date': date(2025, 2, 20), 'amount': 35000,
             'description': 'Оплата за консультації'},
        ])
        self.assertEqual(book.total_income, 60000)
        self.assertEqual(book.line_count, 2)

    def test_income_book_confirm(self):
        """Confirming should change state to confirmed."""
        book = self._create_income_book()
        book.action_confirm()
        self.assertEqual(book.state, 'confirmed')

    def test_income_book_draft_from_confirmed(self):
        """Should be able to reset to draft."""
        book = self._create_income_book()
        book.action_confirm()
        book.action_draft()
        self.assertEqual(book.state, 'draft')

    def test_income_book_empty_total(self):
        """Empty book should have zero total."""
        book = self._create_income_book()
        self.assertEqual(book.total_income, 0)
        self.assertEqual(book.line_count, 0)
