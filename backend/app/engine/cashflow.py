"""Income and spending from transactions (any source: Nessie, mock banks, fixtures).

The window ends at the *latest transaction*, not today, by default. Sandbox data is
often months old, and a window ending today would show $0 and look broken.
"""

import math
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel

from app.domain.models import Transaction
from app.engine.money import to_cents

# Not spending: money coming in, or moving between your own accounts.
# Counting card payments as spending would count every card purchase twice.
NON_SPENDING = frozenset({"income", "interest", "transfer", "payment"})
DAYS_PER_MONTH = 30


class CategoryTotal(BaseModel):
    category: str
    monthly_average: Decimal


class CashFlowSummary(BaseModel):
    start: date  # first transaction in the window
    end: date
    months: int  # months actually averaged over (can be fewer than requested)
    monthly_income: Decimal
    monthly_spending: Decimal
    by_category: list[CategoryTotal]  # biggest first


def summarize(
    transactions: list[Transaction], *, months: int = 3, as_of: date | None = None
) -> CashFlowSummary:
    if months < 1:
        raise ValueError("months must be >= 1")
    end = as_of or max((t.posted_on for t in transactions), default=date.today())
    window_start = end - timedelta(days=DAYS_PER_MONTH * months - 1)
    in_window = [t for t in transactions if window_start <= t.posted_on <= end]

    # Average over the months the data actually covers, not the months asked for:
    # one month of history divided by 3 would show a third of the real income.
    start = min((t.posted_on for t in in_window), default=end)
    covered = max(1, min(months, math.ceil(((end - start).days + 1) / DAYS_PER_MONTH)))

    income = Decimal("0")
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    for t in in_window:
        if t.category == "income" and t.amount > 0:
            income += t.amount
        elif t.amount < 0 and t.category not in NON_SPENDING:
            by_category[t.category] += -t.amount

    categories = sorted(
        (
            CategoryTotal(category=c, monthly_average=to_cents(v / covered))
            for c, v in by_category.items()
        ),
        key=lambda c: c.monthly_average,
        reverse=True,
    )
    return CashFlowSummary(
        start=start,
        end=end,
        months=covered,
        monthly_income=to_cents(income / covered),
        monthly_spending=to_cents(sum(by_category.values(), Decimal("0")) / covered),
        by_category=categories,
    )
