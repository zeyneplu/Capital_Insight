"""Financial health indicators.

Rule for this whole package: pure functions only. No I/O, no LLM, no globals.
Same input -> same output, which makes every number testable and explainable.
The AI coach *calls* these functions; it never does the math itself.

Thresholds are common rules of thumb, kept as named constants so they are easy to
find, discuss with judges, and change.
"""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel

from app.domain.models import Account, AccountType, FinancialProfile
from app.engine.money import to_cents, to_ratio

# Credit utilization: lower is better. Under 30% is the usual guidance; under 10% is excellent.
UTILIZATION_GOOD_BELOW = Decimal("0.10")
UTILIZATION_FAIR_BELOW = Decimal("0.30")

# Emergency fund, in months of expenses.
EMERGENCY_GOOD_MONTHS = Decimal("6")
EMERGENCY_FAIR_MONTHS = Decimal("3")

# Savings rate = share of monthly income not spent.
SAVINGS_RATE_GOOD = Decimal("0.20")
SAVINGS_RATE_FAIR = Decimal("0.10")


class Status(StrEnum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    UNKNOWN = "unknown"  # not enough data; say so instead of guessing


class Indicator(BaseModel):
    key: str
    label: str
    value: Decimal | None
    unit: str  # "ratio" | "months" | "usd_per_year"
    status: Status
    detail: str


class HealthReport(BaseModel):
    customer_id: str
    indicators: list[Indicator]


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------


def credit_utilization(accounts: tuple[Account, ...]) -> Decimal | None:
    """Total card balances / total card limits. None if no card has a known limit."""
    cards = [
        a for a in accounts if a.type is AccountType.CREDIT_CARD and a.credit_limit is not None
    ]
    if not cards:
        return None
    total_limit = sum((a.credit_limit for a in cards), Decimal("0"))
    total_balance = sum((a.balance for a in cards), Decimal("0"))
    return to_ratio(total_balance / total_limit)


def liquid_cash(accounts: tuple[Account, ...]) -> Decimal:
    return sum((a.balance for a in accounts if a.type.is_liquid), Decimal("0"))


def best_deposit_rate(accounts: tuple[Account, ...]) -> Decimal:
    """Best rate on money you could actually move today (CDs and IRAs are locked)."""
    rates = [a.annual_rate for a in accounts if a.type.is_liquid]
    return max(rates, default=Decimal("0"))


def emergency_fund_months(profile: FinancialProfile) -> Decimal | None:
    if not profile.monthly_expenses:  # None or 0 -> can't compute
        return None
    return to_ratio(liquid_cash(profile.accounts) / profile.monthly_expenses)


def savings_rate(profile: FinancialProfile) -> Decimal | None:
    if not profile.monthly_income or profile.monthly_expenses is None:
        return None
    return to_ratio((profile.monthly_income - profile.monthly_expenses) / profile.monthly_income)


def debt_payoff_savings(profile: FinancialProfile) -> Decimal | None:
    """Yearly interest saved by using spare cash to pay down debt that costs more than cash earns.

    "Spare" = liquid cash above a 3-month emergency buffer, so we never tell someone to
    drain their safety net. Highest-APR debt is paid first (the "avalanche" method).
    """
    if profile.monthly_expenses is None:
        return None
    buffer = profile.monthly_expenses * EMERGENCY_FAIR_MONTHS
    spare = max(liquid_cash(profile.accounts) - buffer, Decimal("0"))
    cash_yield = best_deposit_rate(profile.accounts)

    expensive_debts = sorted(
        (a for a in profile.accounts if a.type.is_debt and a.annual_rate > cash_yield),
        key=lambda a: a.annual_rate,
        reverse=True,
    )
    saved = Decimal("0")
    for debt in expensive_debts:
        if spare <= 0:
            break
        paid = min(spare, debt.balance)
        saved += paid * (debt.annual_rate - cash_yield)
        spare -= paid
    return to_cents(saved)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _grade_higher_is_better(value: Decimal | None, good: Decimal, fair: Decimal) -> Status:
    if value is None:
        return Status.UNKNOWN
    if value >= good:
        return Status.GOOD
    return Status.FAIR if value >= fair else Status.POOR


def _grade_lower_is_better(value: Decimal | None, good: Decimal, fair: Decimal) -> Status:
    if value is None:
        return Status.UNKNOWN
    if value < good:
        return Status.GOOD
    return Status.FAIR if value < fair else Status.POOR


def health_report(profile: FinancialProfile) -> HealthReport:
    util = credit_utilization(profile.accounts)
    months = emergency_fund_months(profile)
    rate = savings_rate(profile)
    payoff = debt_payoff_savings(profile)

    indicators = [
        Indicator(
            key="credit_utilization",
            label="Credit utilization",
            value=util,
            unit="ratio",
            status=_grade_lower_is_better(util, UTILIZATION_GOOD_BELOW, UTILIZATION_FAIR_BELOW),
            detail="Share of your total credit limit in use. Under 10% is excellent; 30% or "
            "more tends to hurt credit scores. It is one of the largest score factors.",
        ),
        Indicator(
            key="emergency_fund_months",
            label="Emergency fund",
            value=months,
            unit="months",
            status=_grade_higher_is_better(months, EMERGENCY_GOOD_MONTHS, EMERGENCY_FAIR_MONTHS),
            detail="How many months of expenses your checking and savings could cover. "
            "3 months is a floor; 6 is comfortable.",
        ),
        Indicator(
            key="savings_rate",
            label="Savings rate",
            value=rate,
            unit="ratio",
            status=_grade_higher_is_better(rate, SAVINGS_RATE_GOOD, SAVINGS_RATE_FAIR),
            detail="Share of monthly income you keep. 20% or more is a strong habit.",
        ),
        Indicator(
            key="debt_payoff_savings",
            label="Interest you could stop paying",
            value=payoff,
            unit="usd_per_year",
            status=(
                Status.UNKNOWN if payoff is None else Status.GOOD if payoff == 0 else Status.FAIR
            ),
            detail="Yearly interest saved by paying high-APR debt with cash above a 3-month "
            "emergency buffer, instead of keeping that cash in lower-yield accounts.",
        ),
    ]
    return HealthReport(customer_id=profile.customer_id, indicators=indicators)
