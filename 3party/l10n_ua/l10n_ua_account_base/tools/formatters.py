"""Formatters for Ukrainian localization."""

from datetime import date
from decimal import Decimal


MONTHS_UA = {
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

UNITS = ['', 'один', 'два', 'три', 'чотири', "п'ять", 'шість', 'сім', 'вісім', "дев'ять"]
UNITS_F = ['', 'одна', 'дві', 'три', 'чотири', "п'ять", 'шість', 'сім', 'вісім', "дев'ять"]
TEENS = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять',
         "п'ятнадцять", 'шістнадцять', 'сімнадцять', 'вісімнадцять', "дев'ятнадцять"]
TENS = ['', '', 'двадцять', 'тридцять', 'сорок', "п'ятдесят",
        'шістдесят', 'сімдесят', 'вісімдесят', "дев'яносто"]
HUNDREDS = ['', 'сто', 'двісті', 'триста', 'чотириста', "п'ятсот",
            'шістсот', 'сімсот', 'вісімсот', "дев'ятсот"]

THOUSANDS = ['тисяча', 'тисячі', 'тисяч']
MILLIONS = ['мільйон', 'мільйони', 'мільйонів']
BILLIONS = ['мільярд', 'мільярди', 'мільярдів']

UAH_FORMS = ['гривня', 'гривні', 'гривень']
KOP_FORMS = ['копійка', 'копійки', 'копійок']


def format_date_ua(dt: date, format_type: str = 'long') -> str:
    """Format date in Ukrainian.
    
    Args:
        dt: Date to format
        format_type: 'long' for "15" січня 2026 р., 'short' for 15.01.2026
        
    Returns:
        Formatted date string
    """
    if not dt:
        return ''
    
    if format_type == 'short':
        return dt.strftime('%d.%m.%Y')
    
    day = f'"{dt.day:02d}"'
    month = MONTHS_UA.get(dt.month, '')
    year = f'{dt.year} р.'
    
    return f'{day} {month} {year}'


def format_money_ua(amount: float, currency: str = 'UAH') -> str:
    """Format money amount in Ukrainian format.
    
    Args:
        amount: Amount to format
        currency: Currency code
        
    Returns:
        Formatted amount string (e.g., "1 234,56 грн")
    """
    if amount is None:
        return ''
    
    formatted = f'{amount:,.2f}'.replace(',', ' ').replace('.', ',')
    
    currency_symbols = {
        'UAH': 'грн',
        'USD': 'дол.',
        'EUR': 'євро',
    }
    symbol = currency_symbols.get(currency, currency)
    
    return f'{formatted} {symbol}'


def _get_plural_form(number: int, forms: list) -> str:
    """Get correct plural form for Ukrainian."""
    n = abs(number) % 100
    n1 = n % 10
    
    if 10 < n < 20:
        return forms[2]
    if n1 == 1:
        return forms[0]
    if 2 <= n1 <= 4:
        return forms[1]
    return forms[2]


def _number_to_words_chunk(n: int, feminine: bool = False) -> str:
    """Convert a number (0-999) to Ukrainian words."""
    if n == 0:
        return ''
    
    words = []
    units = UNITS_F if feminine else UNITS
    
    if n >= 100:
        words.append(HUNDREDS[n // 100])
        n %= 100
    
    if n >= 20:
        words.append(TENS[n // 10])
        n %= 10
    elif n >= 10:
        words.append(TEENS[n - 10])
        return ' '.join(words)
    
    if n > 0:
        words.append(units[n])
    
    return ' '.join(words)


def number_to_words_ua(number: int) -> str:
    """Convert integer to Ukrainian words.
    
    Args:
        number: Integer to convert
        
    Returns:
        Number in Ukrainian words
    """
    if number == 0:
        return 'нуль'
    
    if number < 0:
        return 'мінус ' + number_to_words_ua(abs(number))
    
    words = []
    
    if number >= 1_000_000_000:
        billions = number // 1_000_000_000
        words.append(_number_to_words_chunk(billions))
        words.append(_get_plural_form(billions, BILLIONS))
        number %= 1_000_000_000
    
    if number >= 1_000_000:
        millions = number // 1_000_000
        words.append(_number_to_words_chunk(millions))
        words.append(_get_plural_form(millions, MILLIONS))
        number %= 1_000_000
    
    if number >= 1000:
        thousands = number // 1000
        words.append(_number_to_words_chunk(thousands, feminine=True))
        words.append(_get_plural_form(thousands, THOUSANDS))
        number %= 1000
    
    if number > 0:
        words.append(_number_to_words_chunk(number))
    
    return ' '.join(w for w in words if w)


def amount_to_words_ua(amount: float, currency: str = 'UAH') -> str:
    """Convert amount to Ukrainian words.
    
    Args:
        amount: Amount to convert
        currency: Currency code (only UAH supported for now)
        
    Returns:
        Amount in Ukrainian words (e.g., "одна тисяча двісті тридцять чотири гривні 56 копійок")
    """
    if amount is None:
        return ''
    
    amount = Decimal(str(amount)).quantize(Decimal('0.01'))
    hryvni = int(amount)
    kopiyky = int((amount - hryvni) * 100)
    
    result = []
    
    if hryvni == 0:
        result.append('нуль')
        result.append(UAH_FORMS[2])
    else:
        result.append(number_to_words_ua(hryvni))
        result.append(_get_plural_form(hryvni, UAH_FORMS))
    
    result.append(f'{kopiyky:02d}')
    result.append(_get_plural_form(kopiyky, KOP_FORMS))
    
    return ' '.join(result)
