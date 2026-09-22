"""Unit tests для tools.transforms."""

from datetime import date
from decimal import Decimal

from odoo.tests import TransactionCase, tagged

from ..tools.transforms import apply_transform, TransformError


@tagged('post_install', '-at_install')
class TestTransforms(TransactionCase):

    def test_none_passthrough(self):
        self.assertEqual(apply_transform('abc', 'none'), 'abc')
        self.assertEqual(apply_transform('abc', None), 'abc')
        self.assertEqual(apply_transform('abc', ''), 'abc')

    def test_empty_value_passthrough(self):
        self.assertIsNone(apply_transform(None, 'upper'))
        self.assertEqual(apply_transform('', 'upper'), '')

    def test_strip(self):
        self.assertEqual(apply_transform('  hello  ', 'strip'), 'hello')

    def test_upper_lower(self):
        self.assertEqual(apply_transform('Hello', 'upper'), 'HELLO')
        self.assertEqual(apply_transform('Hello', 'lower'), 'hello')

    def test_replace_comma(self):
        self.assertEqual(apply_transform('1,5', 'replace_comma'), '1.5')

    def test_to_float(self):
        self.assertEqual(apply_transform('1.5', 'to_float'), 1.5)
        self.assertEqual(apply_transform('1,5', 'to_float'), 1.5)
        self.assertEqual(apply_transform(' 42 ', 'to_float'), 42.0)

    def test_to_float_invalid(self):
        with self.assertRaises(TransformError):
            apply_transform('not a number', 'to_float')

    def test_to_decimal(self):
        self.assertEqual(apply_transform('1.50', 'to_decimal'), Decimal('1.50'))
        self.assertEqual(apply_transform('1,50', 'to_decimal'), Decimal('1.50'))

    def test_parse_date_default_format(self):
        self.assertEqual(apply_transform('2026-04-17', 'parse_date'), date(2026, 4, 17))

    def test_parse_date_custom_format(self):
        self.assertEqual(
            apply_transform('17/04/2026', 'parse_date', '%d/%m/%Y'),
            date(2026, 4, 17),
        )

    def test_parse_date_invalid(self):
        with self.assertRaises(TransformError):
            apply_transform('not a date', 'parse_date')

    def test_multiply(self):
        self.assertEqual(apply_transform('10', 'multiply', '1.5'), 15.0)
        self.assertEqual(apply_transform('1,5', 'multiply', '2'), 3.0)

    def test_multiply_no_param(self):
        with self.assertRaises(TransformError):
            apply_transform('10', 'multiply')

    def test_unknown_transform(self):
        with self.assertRaises(TransformError):
            apply_transform('x', 'nonexistent')
