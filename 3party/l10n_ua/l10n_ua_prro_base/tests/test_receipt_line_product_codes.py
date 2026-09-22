"""Рядок чека бере УКТ ЗЕД з номенклатури, а не з пам'яті касира (#254)."""

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReceiptLineProductCodes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env['l10n_ua.prro.config'].create({
            'name': 'Каса (коди)',
            'provider': 'checkbox',
            'company_id': cls.env.company.id,
        })
        cls.shift = cls.env['l10n_ua.prro.shift'].create({'config_id': cls.config.id})
        cls.product = cls.env['product.product'].create({
            'name': 'Горілка 0,5', 'type': 'consu', 'uktzed_code': '2208.60.11.00',
        })

    def _new_line(self, receipt, **vals):
        line = self.env['l10n_ua.prro.receipt.line'].new(dict({
            'receipt_id': receipt.id,
        }, **vals))
        line._onchange_product_id()
        return line

    def test_code_and_name_come_from_the_product(self):
        receipt = self.env['l10n_ua.prro.receipt'].create({'shift_id': self.shift.id})
        line = self._new_line(receipt, product_id=self.product.id)

        self.assertEqual(line.uktzed_code, '2208601100',
                         'код підакцизного товару має підтягнутись із номенклатури')
        self.assertEqual(line.name, 'Горілка 0,5')

    def test_a_hand_typed_code_is_not_overwritten(self):
        """Касир міг виправити код під конкретну партію — не затираємо."""
        receipt = self.env['l10n_ua.prro.receipt'].create({'shift_id': self.shift.id})
        line = self._new_line(
            receipt, product_id=self.product.id,
            uktzed_code='2208601900', name='Своя назва')

        self.assertEqual(line.uktzed_code, '2208601900')
        self.assertEqual(line.name, 'Своя назва')

    def test_line_without_a_product_is_left_alone(self):
        receipt = self.env['l10n_ua.prro.receipt'].create({'shift_id': self.shift.id})
        line = self._new_line(receipt, name='Ручний рядок')

        self.assertFalse(line.uktzed_code)
        self.assertEqual(line.name, 'Ручний рядок')
