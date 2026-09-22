"""Рядки ПН мають відповідати рядкам документа — по складу, базі та ставці."""
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install', 'l10n_ua_account_vat')
class TestTaxInvoiceLines(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.l10n_ua_is_vat_payer = True
        cls.customer = cls.env['res.partner'].create({'name': 'Покупець ПН'})
        cls.vat_20 = cls.env['account.tax'].create({
            'name': 'ПДВ 20% (тест)', 'amount': 20.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': cls.env.company.id,
        })
        cls.vat_20_incl = cls.env['account.tax'].create({
            'name': 'ПДВ 20% у ціні (тест)', 'amount': 20.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'price_include_override': 'tax_included',
            'company_id': cls.env.company.id,
        })
        cls.vat_7 = cls.env['account.tax'].create({
            'name': 'ПДВ 7% (тест)', 'amount': 7.0, 'amount_type': 'percent',
            'type_tax_use': 'sale', 'company_id': cls.env.company.id,
        })
        cls.vat_20_group = cls.env['account.tax'].create({
            'name': 'ПДВ 20% у групі (тест)', 'amount_type': 'group',
            'type_tax_use': 'sale', 'company_id': cls.env.company.id,
            'children_tax_ids': [(6, 0, cls.vat_20.ids)],
        })
        cls.other_currency = cls.setup_other_currency('EUR')

    def _invoice(self, lines, **move_vals):
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': '2025-05-05',
            'date': '2025-05-05',
            'invoice_line_ids': [(0, 0, vals) for vals in lines],
            **move_vals,
        })
        move.action_post()
        return move

    def _tax_invoice(self, move):
        move.action_create_tax_invoice()
        return self.env['l10n_ua.tax.invoice'].search([('move_id', '=', move.id)], limit=1)

    def test_lines_are_created_at_all(self):
        """Головна регресія: фільтр display_type лишав ПН геть без рядків."""
        move = self._invoice([
            {'name': 'товар', 'quantity': 10, 'price_unit': 100.0,
             'tax_ids': [(6, 0, self.vat_20.ids)]},
            {'name': 'послуга', 'quantity': 1, 'price_unit': 500.0,
             'tax_ids': [(6, 0, self.vat_20.ids)]},
        ])

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(len(tax_invoice.line_ids), 2,
                          'ПН має містити стільки ж товарних рядків, скільки документ')
        self.assertGreater(tax_invoice.total_vat, 0.0,
                            'сума ПДВ у ПН не може бути нульовою для оподаткованої операції')

    def test_sections_and_notes_are_skipped(self):
        """Секції та примітки — оформлення документа, у ПН їм місця немає."""
        move = self._invoice([
            {'name': 'Розділ', 'display_type': 'line_section'},
            {'name': 'товар', 'quantity': 2, 'price_unit': 50.0,
             'tax_ids': [(6, 0, self.vat_20.ids)]},
            {'name': 'Примітка', 'display_type': 'line_note'},
        ])

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(len(tax_invoice.line_ids), 1)
        self.assertEqual(tax_invoice.line_ids.name, 'товар')

    def test_discount_is_reflected_in_base(self):
        """База ПН має збігатися з базою документа, а не ігнорувати знижку."""
        move = self._invoice([
            {'name': 'товар', 'quantity': 10, 'price_unit': 100.0, 'discount': 10.0,
             'tax_ids': [(6, 0, self.vat_20.ids)]},
        ])
        invoice_line = move.invoice_line_ids

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(invoice_line.price_subtotal, 900.0)
        self.assertAlmostEqual(tax_invoice.line_ids.base_amount, 900.0, places=2,
                                msg='знижка на рядку загубилась у ПН')
        self.assertAlmostEqual(tax_invoice.line_ids.vat_amount, 180.0, places=2)

    def test_price_included_tax_gives_net_base(self):
        """Для ціни з ПДВ база в ПН — без податку, а не разом із ним."""
        move = self._invoice([
            {'name': 'товар', 'quantity': 1, 'price_unit': 120.0,
             'tax_ids': [(6, 0, self.vat_20_incl.ids)]},
        ])

        tax_invoice = self._tax_invoice(move)

        self.assertAlmostEqual(tax_invoice.line_ids.base_amount, 100.0, places=2)
        self.assertAlmostEqual(tax_invoice.line_ids.vat_amount, 20.0, places=2)

    def test_rate_comes_from_the_line_tax(self):
        move = self._invoice([
            {'name': 'ліки', 'quantity': 1, 'price_unit': 200.0,
             'tax_ids': [(6, 0, self.vat_7.ids)]},
        ])

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(tax_invoice.line_ids.vat_rate, '7')

    def test_line_without_vat_is_not_taxed_at_twenty(self):
        """Рядок без ПДВ не має ставати оподаткованим за 20% через дефолт."""
        move = self._invoice([
            {'name': 'звільнена операція', 'quantity': 1, 'price_unit': 300.0,
             'tax_ids': []},
        ])

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(tax_invoice.line_ids.vat_rate, 'exempt')
        self.assertEqual(tax_invoice.line_ids.vat_amount, 0.0)

    def test_mixed_rates_keep_their_own_lines(self):
        """Кожен рядок несе свою ставку, а не ставку сусіда."""
        move = self._invoice([
            {'name': 'товар 20', 'quantity': 1, 'price_unit': 100.0,
             'tax_ids': [(6, 0, self.vat_20.ids)]},
            {'name': 'ліки 7', 'quantity': 1, 'price_unit': 100.0,
             'tax_ids': [(6, 0, self.vat_7.ids)]},
            {'name': 'без ПДВ', 'quantity': 1, 'price_unit': 100.0, 'tax_ids': []},
        ])

        tax_invoice = self._tax_invoice(move)
        by_name = {line.name: line for line in tax_invoice.line_ids}

        self.assertEqual(by_name['товар 20'].vat_rate, '20')
        self.assertEqual(by_name['ліки 7'].vat_rate, '7')
        self.assertEqual(by_name['без ПДВ'].vat_rate, 'exempt')
        self.assertAlmostEqual(tax_invoice.total_vat, 27.0, places=2)

    def test_grouped_tax_is_not_mistaken_for_exempt(self):
        """ПДВ у складі групи податків — це все одно ПДВ."""
        move = self._invoice([
            {'name': 'товар', 'quantity': 1, 'price_unit': 100.0,
             'tax_ids': [(6, 0, self.vat_20_group.ids)]},
        ])

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(tax_invoice.line_ids.vat_rate, '20')
        self.assertAlmostEqual(tax_invoice.line_ids.vat_amount, 20.0, places=2)

    def test_amounts_are_converted_to_company_currency(self):
        """ПН завжди у гривні, навіть якщо документ — у валюті."""
        move = self._invoice(
            [{'name': 'товар', 'quantity': 2, 'price_unit': 500.0,
              'tax_ids': [(6, 0, self.vat_20.ids)]}],
            currency_id=self.other_currency.id,
        )
        invoice_line = move.invoice_line_ids
        # Еталон рахуємо перерахунком курсу — незалежно від того, що код
        # бере суму з проводки, і без прив'язки до курсу тестової фікстури.
        expected_base = self.other_currency._convert(
            invoice_line.price_subtotal, self.env.company.currency_id,
            self.env.company, move.invoice_date)

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(tax_invoice.currency_id, self.env.company.currency_id)
        self.assertNotEqual(expected_base, invoice_line.price_subtotal,
                            'фікстура має давати курс, відмінний від 1:1')
        self.assertAlmostEqual(tax_invoice.line_ids.base_amount, expected_base, places=2,
                               msg='база ПН лишилась у валюті документа')

    def test_credit_note_reduces_liability(self):
        """РК має зменшувати зобов'язання й посилатися на оригінальну ПН.

        Доти цикл не виконувався й РК виходив порожній, тож знак ніде не
        проявлявся; тепер порожня гілка стала документом.
        """
        move = self._invoice([
            {'name': 'товар', 'quantity': 2, 'price_unit': 100.0,
             'tax_ids': [(6, 0, self.vat_20.ids)]},
        ])
        original = self._tax_invoice(move)

        refund = move._reverse_moves([{
            'invoice_date': '2025-05-10',
            'date': '2025-05-10',
            'ref': 'повернення товару',
        }])
        refund.action_post()
        correction = self._tax_invoice(refund)

        self.assertEqual(correction.doc_type, 'rk')
        self.assertEqual(correction.line_ids.quantity, -2.0)
        self.assertAlmostEqual(correction.line_ids.price_unit, 100.0, places=2,
                               msg='ціна в РК не змінюється — змінюється кількість')
        self.assertAlmostEqual(correction.total_vat, -40.0, places=2,
                               msg='РК зменшує зобов\'язання, а не збільшує')
        self.assertEqual(correction.original_invoice_id, original)
        self.assertEqual(correction.reason, 'повернення товару')

    def test_total_vat_matches_the_document(self):
        """Сума ПДВ у ПН має збігатися з податком документа.

        Кількість 3 і знижка дають базу 379.99, що не ділиться на копійки —
        саме тут округлення ціни до двох знаків давало 126.66 × 3 = 379.98.
        """
        move = self._invoice([
            {'name': 'товар', 'quantity': 3, 'price_unit': 133.33, 'discount': 5.0,
             'tax_ids': [(6, 0, self.vat_20.ids)]},
        ])

        tax_invoice = self._tax_invoice(move)

        self.assertEqual(move.invoice_line_ids.price_subtotal, 379.99)
        self.assertEqual(tax_invoice.line_ids.base_amount, 379.99)
        self.assertEqual(tax_invoice.total_vat, move.amount_tax)
