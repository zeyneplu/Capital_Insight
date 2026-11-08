from datetime import date
from decimal import Decimal

import pytest

from app.domain.models import Transaction
from app.engine.cashflow import summarize


def tx(day: str, amount: str, category: str) -> Transaction:
    return Transaction(
        id=f"{day}{amount}{category}",
        account_id="a",
        posted_on=date.fromisoformat(day),
        amount=Decimal(amount),
        description=category,
        category=category,
    )


def test_monthly_income_and_spending_skip_transfers():
    txns = [
        tx("2026-10-01", "1600", "income"),
        tx("2026-10-15", "1600", "income"),
        tx("2026-10-01", "-1100", "housing"),
        tx("2026-10-05", "-90", "groceries"),
        tx("2026-10-20", "-450", "transfer"),  # card payment: NOT spending
        tx("2026-10-28", "10", "interest"),
    ]
    s = summarize(txns, months=1)

    assert s.end == date(2026, 10, 28)  # anchored to the latest transaction
    assert s.monthly_income == Decimal("3200.00")
    assert s.monthly_spending == Decimal("1190.00")
    assert [(c.category, c.monthly_average) for c in s.by_category] == [
        ("housing", Decimal("1100.00")),
        ("groceries", Decimal("90.00")),
    ]


def test_averages_over_months_and_ignores_old_data():
    txns = [
        tx("2026-10-20", "-300", "dining"),
        tx("2026-09-20", "-300", "dining"),
        tx("2026-01-01", "-9999", "dining"),  # outside a 2-month window
    ]
    s = summarize(txns, months=2)
    assert s.by_category[0].monthly_average == Decimal("300.00")


def test_averages_only_over_months_the_data_covers():
    # One month of history, but 3 months requested (the default).
    txns = [tx("2026-10-01", "1600", "income"), tx("2026-10-15", "1600", "income"),
            tx("2026-10-20", "-90", "groceries")]  # fmt: skip
    s = summarize(txns, months=3)
    assert s.months == 1
    assert s.start == date(2026, 10, 1)
    assert s.monthly_income == Decimal("3200.00")  # not 1066.67


def test_empty_is_zero_not_an_error():
    s = summarize([], as_of=date(2026, 11, 7))
    assert s.monthly_income == s.monthly_spending == Decimal("0.00")
    assert s.by_category == []


def test_rejects_bad_window():
    with pytest.raises(ValueError):
        summarize([], months=0)
