"""УКТ ЗЕД і ДКПП на номенклатурі: нормалізація, формат, вибір коду за типом."""
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install', 'l10n_ua_product_base')
class TestProductCodes(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Product = cls.env['product.template']

    def _goods(self, **vals):
        return self.Product.create(dict({'name': 'Ноутбук', 'type': 'consu'}, **vals))

    def _service(self, **vals):
        return self.Product.create(dict({'name': 'Розробка ПЗ', 'type': 'service'}, **vals))

    # ------------------------------------------------------------ нормалізація

    def test_separators_are_stripped_on_create(self):
        """Код із митної декларації приходить із крапками — зберігаємо цифри.

        У XML ЄРПН іде голий рядок цифр, тож нормалізувати треба на записі:
        інакше константа в базі й константа в документі — різні речі.
        """
        for written, stored in [
            ('8471.30.00.00', '8471300000'),
            ('8471 30 00 00', '8471300000'),
            ('  8471300000  ', '8471300000'),
            ('8471-30-00-00', '8471300000'),
        ]:
            with self.subTest(written=written):
                self.assertEqual(self._goods(uktzed_code=written).uktzed_code, stored)

    def test_separators_are_stripped_on_write(self):
        product = self._goods(uktzed_code='8471300000')
        product.uktzed_code = '9403.20.80.00'
        self.assertEqual(product.uktzed_code, '9403208000')

    # ------------------------------------------------------------ формат

    def test_classifier_levels_are_accepted(self):
        for code in ('8471', '847130', '84713000', '8471300000'):
            with self.subTest(code=code):
                self.assertEqual(self._goods(uktzed_code=code).uktzed_code, code)

    def test_length_outside_the_classifier_levels_is_refused(self):
        """П'ять цифр — не рівень УКТ ЗЕД, а обірваний код: ЄРПН його відкине."""
        for code in ('847', '84713', '847130000', '84713000001'):
            with self.subTest(code=code):
                with self.assertRaises(ValidationError):
                    self._goods(uktzed_code=code)

    def test_letters_are_refused(self):
        with self.assertRaises(ValidationError):
            self._goods(uktzed_code='8471AB0000')

    def test_empty_code_is_allowed(self):
        """Порожнє поле — законний стан: код обов'язковий у ПН, не в довіднику."""
        self.assertFalse(self._goods().uktzed_code)
        self.assertFalse(self._goods(uktzed_code=False).uktzed_code)

    def test_dkpp_shape(self):
        for code in ('62', '62.01', '62.01.11', '62.01.11-00', '62.01.11-00.00'):
            with self.subTest(code=code):
                self.assertEqual(self._service(dkpp_code=code).dkpp_code, code)
        for code in ('62.1.11', 'ХХ.01.11', '62.01.11.00.00', '62-01', '62.01-00'):
            with self.subTest(code=code):
                with self.assertRaises(ValidationError):
                    self._service(dkpp_code=code)

    # ------------------------------------------------------ вибір за типом

    def test_goods_give_uktzed_only(self):
        product = self._goods(uktzed_code='8471300000', dkpp_code='62.01.11-00.00')
        self.assertEqual(
            product._l10n_ua_product_codes(),
            {'uktzed_code': '8471300000', 'dkpp_code': False},
        )

    def test_service_gives_dkpp_only(self):
        product = self._service(uktzed_code='8471300000', dkpp_code='62.01.11-00.00')
        self.assertEqual(
            product._l10n_ua_product_codes(),
            {'uktzed_code': False, 'dkpp_code': '62.01.11-00.00'},
        )

    def test_missing_product_gives_both_keys_empty(self):
        """Рядок без номенклатури має затерти старий код, а не лишити його."""
        self.assertEqual(
            self.env['product.product']._l10n_ua_product_codes(),
            {'uktzed_code': False, 'dkpp_code': False},
        )

    def test_variant_delegates_to_template(self):
        """`_inherits` передає поля, але не методи — варіант має свій виклик."""
        product = self._goods(uktzed_code='8471300000')
        variant = product.product_variant_id
        self.assertEqual(variant.uktzed_code, '8471300000')
        self.assertEqual(
            variant._l10n_ua_product_codes(),
            {'uktzed_code': '8471300000', 'dkpp_code': False},
        )
