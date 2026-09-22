"""Трансформації значень з полів mapping."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class TransformError(ValueError):
    """Raised when a transform cannot be applied to a value."""


def apply_transform(value: Any, transform: str, param: str | None = None) -> Any:
    """Застосовує трансформацію до значення.

    Returns: transformed value.
    Raises: TransformError якщо трансформацію застосувати неможливо.
    """
    if value is None or value == '':
        return value

    if transform in (None, '', 'none'):
        return value

    if transform == 'strip':
        return str(value).strip()

    if transform == 'upper':
        return str(value).upper()

    if transform == 'lower':
        return str(value).lower()

    if transform == 'replace_comma':
        return str(value).replace(',', '.')

    if transform == 'to_float':
        try:
            return float(str(value).replace(',', '.').strip())
        except (ValueError, TypeError) as e:
            raise TransformError(f"Cannot convert {value!r} to float: {e}") from e

    if transform == 'to_decimal':
        try:
            return Decimal(str(value).replace(',', '.').strip())
        except (InvalidOperation, ValueError) as e:
            raise TransformError(f"Cannot convert {value!r} to Decimal: {e}") from e

    if transform == 'parse_date':
        if isinstance(value, (date, datetime)):
            return value if isinstance(value, date) else value.date()
        fmt = param or '%Y-%m-%d'
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError as e:
            raise TransformError(f"Cannot parse {value!r} as date with format {fmt!r}: {e}") from e

    if transform == 'multiply':
        if not param:
            raise TransformError("multiply transform requires transform_param (factor)")
        try:
            factor = float(param)
            return float(str(value).replace(',', '.').strip()) * factor
        except (ValueError, TypeError) as e:
            raise TransformError(f"Cannot apply multiply to {value!r}: {e}") from e

    raise TransformError(f"Unknown transform: {transform!r}")
