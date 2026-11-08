"""Rounding rules in one place, so every number the user sees is rounded the same way."""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
RATIO = Decimal("0.0001")  # 4 places: 0.2400 == 24.00%


def to_cents(amount: Decimal) -> Decimal:
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def to_cents_up(amount: Decimal) -> Decimal:
    """Round a required payment *up*, so paying it is guaranteed to reach the goal."""
    return amount.quantize(CENT, rounding=ROUND_CEILING)


def to_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO, rounding=ROUND_HALF_UP)
