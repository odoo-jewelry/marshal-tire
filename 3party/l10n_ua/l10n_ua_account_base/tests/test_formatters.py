"""Tests for Ukrainian formatters (dates, money, numbers to words)."""

from datetime import date

from odoo.tests import TransactionCase

from ..tools.formatters import (
    format_date_ua,
    format_money_ua,
    number_to_words_ua,
    amount_to_words_ua,
)


class TestFormatDateUa(TransactionCase):
    """Test cases for Ukrainian date formatting."""

    def test_format_date_long(self):
        """Test long date format."""
        dt = date(2026, 1, 15)
        result = format_date_ua(dt, 'long')
        self.assertEqual(result, '"15" січня 2026 р.')

    def test_format_date_long_all_months(self):
        """Test long format for all months."""
        expected_months = {
            1: 'січня',
            2: 'лютого',
            3: 'березня',
            4: 'квітня',
            5: 'травня',
            6: 'червня',
            7: 'липня',
            8: 'серпня',
            9: 'вересня',
            10: 'жовтня',
            11: 'листопада',
            12: 'грудня',
        }
        for month, month_name in expected_months.items():
            dt = date(2026, month, 1)
            result = format_date_ua(dt, 'long')
            self.assertIn(month_name, result, f'Month {month} should be {month_name}')

    def test_format_date_short(self):
        """Test short date format."""
        dt = date(2026, 1, 15)
        result = format_date_ua(dt, 'short')
        self.assertEqual(result, '15.01.2026')

    def test_format_date_none(self):
        """Test formatting None date."""
        result = format_date_ua(None)
        self.assertEqual(result, '')


class TestFormatMoneyUa(TransactionCase):
    """Test cases for Ukrainian money formatting."""

    def test_format_money_uah(self):
        """Test UAH formatting."""
        test_cases = [
            (1234.56, '1 234,56 грн'),
            (0.01, '0,01 грн'),
            (1000000.00, '1 000 000,00 грн'),
        ]
        for amount, expected in test_cases:
            result = format_money_ua(amount, 'UAH')
            self.assertEqual(result, expected, f'Amount {amount} should be formatted as {expected}')

    def test_format_money_usd(self):
        """Test USD formatting."""
        result = format_money_ua(100.50, 'USD')
        self.assertEqual(result, '100,50 дол.')

    def test_format_money_eur(self):
        """Test EUR formatting."""
        result = format_money_ua(100.50, 'EUR')
        self.assertEqual(result, '100,50 євро')

    def test_format_money_none(self):
        """Test formatting None amount."""
        result = format_money_ua(None)
        self.assertEqual(result, '')


class TestNumberToWordsUa(TransactionCase):
    """Test cases for number to Ukrainian words conversion."""

    def test_zero(self):
        """Test zero."""
        self.assertEqual(number_to_words_ua(0), 'нуль')

    def test_units(self):
        """Test single digit numbers."""
        expected = {
            1: 'один',
            2: 'два',
            3: 'три',
            4: 'чотири',
            5: "п'ять",
            6: 'шість',
            7: 'сім',
            8: 'вісім',
            9: "дев'ять",
        }
        for num, word in expected.items():
            self.assertEqual(number_to_words_ua(num), word)

    def test_teens(self):
        """Test numbers 10-19."""
        expected = {
            10: 'десять',
            11: 'одинадцять',
            12: 'дванадцять',
            15: "п'ятнадцять",
            19: "дев'ятнадцять",
        }
        for num, word in expected.items():
            self.assertEqual(number_to_words_ua(num), word)

    def test_tens(self):
        """Test tens."""
        expected = {
            20: 'двадцять',
            30: 'тридцять',
            40: 'сорок',
            50: "п'ятдесят",
            90: "дев'яносто",
        }
        for num, word in expected.items():
            self.assertEqual(number_to_words_ua(num), word)

    def test_hundreds(self):
        """Test hundreds."""
        expected = {
            100: 'сто',
            200: 'двісті',
            300: 'триста',
            500: "п'ятсот",
        }
        for num, word in expected.items():
            self.assertEqual(number_to_words_ua(num), word)

    def test_thousands(self):
        """Test thousands with feminine forms."""
        expected = {
            1000: 'одна тисяча',
            2000: 'дві тисячі',
            5000: "п'ять тисяч",
            21000: 'двадцять одна тисяча',
        }
        for num, word in expected.items():
            self.assertEqual(number_to_words_ua(num), word, f'{num} should be {word}')

    def test_complex_numbers(self):
        """Test complex numbers."""
        expected = {
            123: 'сто двадцять три',
            1234: 'одна тисяча двісті тридцять чотири',
            1000000: 'один мільйон',
            1000001: 'один мільйон один',
        }
        for num, word in expected.items():
            self.assertEqual(number_to_words_ua(num), word, f'{num} should be {word}')

    def test_negative_numbers(self):
        """Test negative numbers."""
        result = number_to_words_ua(-5)
        self.assertEqual(result, "мінус п'ять")


class TestAmountToWordsUa(TransactionCase):
    """Test cases for amount to Ukrainian words conversion."""

    def test_simple_amounts(self):
        """Test simple amounts."""
        expected = {
            1.00: 'один гривня 00 копійок',
            2.00: 'два гривні 00 копійок',
            5.00: "п'ять гривень 00 копійок",
            21.00: 'двадцять один гривня 00 копійок',
        }
        for amount, word in expected.items():
            result = amount_to_words_ua(amount)
            self.assertEqual(result, word, f'{amount} should be {word}')

    def test_amounts_with_kopiyky(self):
        """Test amounts with kopiyky."""
        expected = {
            1.01: 'один гривня 01 копійка',
            1.02: 'один гривня 02 копійки',
            1.05: 'один гривня 05 копійок',
            1.21: 'один гривня 21 копійка',
        }
        for amount, word in expected.items():
            result = amount_to_words_ua(amount)
            self.assertEqual(result, word, f'{amount} should be {word}')

    def test_zero_amount(self):
        """Test zero amount."""
        result = amount_to_words_ua(0.00)
        self.assertEqual(result, 'нуль гривень 00 копійок')

    def test_large_amount(self):
        """Test large amount."""
        result = amount_to_words_ua(1234567.89)
        self.assertIn('мільйон', result)
        self.assertIn('тисяч', result)
        self.assertIn('89 копійок', result)

    def test_none_amount(self):
        """Test None amount."""
        result = amount_to_words_ua(None)
        self.assertEqual(result, '')
