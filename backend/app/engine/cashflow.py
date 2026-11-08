"""Income and spending from transactions (any source: Nessie, mock banks, fixtures).

The window ends at the *latest transaction*, not today, by default. Sandbox data is
often months old, and a window ending today would show $0 and look broken.
"""

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
    start: date
    end: date
    months: int
    monthly_income: Decimal
    monthly_spending: Decimal
    by_category: list[CategoryTotal]  # biggest first


def summarize(
    transactions: list[Transaction], *, months: int = 3, as_of: date | None = None
) -> CashFlowSummary:
    if months < 1:
        raise ValueError("months must be >= 1")
    end = as_of or max((t.posted_on for t in transactions), default=date.today())
    start = end - timedelta(days=DAYS_PER_MONTH * months - 1)

    income = Decimal("0")
    by_category: dict[str, Decimal] = defaultdict(Decimal)
    for t in transactions:
        if not start <= t.posted_on <= end:
            continue
        if t.category == "income" and t.amount > 0:
            income += t.amount
        elif t.amount < 0 and t.category not in NON_SPENDING:
            by_category[t.category] += -t.amount

    categories = sorted(
        (
            CategoryTotal(category=c, monthly_average=to_cents(v / months))
            for c, v in by_category.items()
        ),
        key=lambda c: c.monthly_average,
        reverse=True,
    )
    return CashFlowSummary(
        start=start,
        end=end,
        months=months,
        monthly_income=to_cents(income / months),
        monthly_spending=to_cents(sum(by_category.values(), Decimal("0")) / months),
        by_category=categories,
    )
