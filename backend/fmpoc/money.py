"""Money helpers: API uses decimal strings with at most 2 decimal places; storage uses integer cents."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

MAX_CENTS = 10**13  # 100 billion; sensible upper bound (BR-097)


def parse_amount(value, *, allow_negative: bool = False, allow_zero: bool = True) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("amount is required")
    if isinstance(value, float):
        value = repr(value)
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError("amount must be a decimal number") from None
    if not d.is_finite():
        raise ValueError("amount must be a finite decimal number")
    if d.as_tuple().exponent < -2:  # type: ignore[operator]
        raise ValueError("amount may have at most 2 decimal places")
    cents = int(d * 100)
    if abs(cents) >= MAX_CENTS:
        raise ValueError("amount is out of range")
    if cents < 0 and not allow_negative:
        raise ValueError("amount cannot be negative")
    if cents == 0 and not allow_zero:
        raise ValueError("amount must be greater than zero")
    return cents


def fmt(cents: int | None) -> str | None:
    if cents is None:
        return None
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    return f"{sign}{c // 100}.{c % 100:02d}"
