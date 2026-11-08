"""Goal planning and "what if" simulation for debt accounts.

Example goal from our whiteboard: "Raise my credit score" -> get card utilization
to X% -> in N months -> how much do I pay each month?
"""

from decimal import Decimal

from pydantic import BaseModel

from app.domain.errors import InvalidRequestError
from app.domain.models import Account, AccountType, FinancialProfile
from app.engine.money import to_cents, to_cents_up, to_ratio

MAX_MONTHS = 360
MONTHS_PER_YEAR = Decimal("12")

ASSUMPTIONS = (
    "No new purchases on this account during the plan.",
    "Interest accrues monthly at APR / 12 (cards actually use a daily rate, so real "
    "numbers can differ by a few cents).",
    "Lower utilization usually helps a credit score, but no score change is guaranteed.",
)


class Projection(BaseModel):
    account_id: str
    monthly_payment: Decimal
    months: int
    balances: list[Decimal]  # balance at the end of each month; balances[0] is today
    total_interest: Decimal
    total_paid: Decimal
    paid_off_in_month: int | None  # first month the balance hits 0, if it does
    assumptions: list[str]


class UtilizationPlan(BaseModel):
    account_id: str
    credit_limit: Decimal
    current_balance: Decimal
    current_utilization: Decimal
    target_utilization: Decimal
    target_balance: Decimal
    months: int
    monthly_payment: Decimal
    projection: Projection


# ---------------------------------------------------------------------------
# Pure math
# ---------------------------------------------------------------------------


def _validate_months(months: int) -> None:
    if not 1 <= months <= MAX_MONTHS:
        raise InvalidRequestError(f"months must be between 1 and {MAX_MONTHS}")


def simulate(
    balance: Decimal, annual_rate: Decimal, monthly_payment: Decimal, months: int
) -> tuple[list[Decimal], Decimal, Decimal, int | None]:
    """Month-by-month amortization. Returns (balances, total_interest, total_paid, payoff_month)."""
    _validate_months(months)
    if monthly_payment < 0:
        raise InvalidRequestError("monthly_payment cannot be negative")

    rate = annual_rate / MONTHS_PER_YEAR
    balances = [to_cents(balance)]
    total_interest = total_paid = Decimal("0")
    payoff_month: int | None = None

    current = balances[0]
    for month in range(1, months + 1):
        interest = to_cents(current * rate)
        payment = min(monthly_payment, current + interest)  # never overpay
        current = current + interest - payment
        total_interest += interest
        total_paid += payment
        balances.append(current)
        if current == 0 and payoff_month is None:
            payoff_month = month
    return balances, total_interest, total_paid, payoff_month


def required_monthly_payment(
    balance: Decimal, target_balance: Decimal, annual_rate: Decimal, months: int
) -> Decimal:
    """Smallest whole-cent payment that brings `balance` to <= `target_balance` in `months`.

    Closed form (future value of an annuity):
        B_n = B_0 (1+r)^n - P ((1+r)^n - 1) / r   ->   solve for P with B_n = target
    then verified by simulation, because monthly cent rounding can shift it by a cent.
    """
    _validate_months(months)
    if balance <= target_balance:
        return Decimal("0")

    r = annual_rate / MONTHS_PER_YEAR
    if r == 0:
        payment = (balance - target_balance) / months
    else:
        growth = (1 + r) ** months
        payment = (balance * growth - target_balance) * r / (growth - 1)
    payment = to_cents_up(payment)

    # Verification loop: bounded, normally runs 0-1 times.
    for _ in range(months + 1):
        balances, *_ = simulate(balance, annual_rate, payment, months)
        if balances[-1] <= target_balance:
            return payment
        payment += Decimal("0.01")
    raise AssertionError("payment search did not converge")  # unreachable in practice


# ---------------------------------------------------------------------------
# Use cases (take the domain model, return API-ready results)
# ---------------------------------------------------------------------------


def _debt_account(profile: FinancialProfile, account_id: str) -> Account:
    account = profile.account(account_id)
    if not account.type.is_debt:
        raise InvalidRequestError(f"Account {account_id!r} is not a credit card or loan")
    return account


def project(
    profile: FinancialProfile, account_id: str, monthly_payment: Decimal, months: int
) -> Projection:
    """What if I pay `monthly_payment` every month for `months` months?"""
    account = _debt_account(profile, account_id)
    balances, interest, paid, payoff = simulate(
        account.balance, account.annual_rate, monthly_payment, months
    )
    return Projection(
        account_id=account.id,
        monthly_payment=to_cents(monthly_payment),
        months=months,
        balances=balances,
        total_interest=interest,
        total_paid=paid,
        paid_off_in_month=payoff,
        assumptions=list(ASSUMPTIONS),
    )


def plan_utilization_goal(
    profile: FinancialProfile, account_id: str, target_utilization: Decimal, months: int
) -> UtilizationPlan:
    account = _debt_account(profile, account_id)
    if account.type is not AccountType.CREDIT_CARD or account.credit_limit is None:
        raise InvalidRequestError(
            f"Account {account_id!r} has no known credit limit, so utilization can't be planned"
        )
    if not Decimal("0") <= target_utilization < Decimal("1"):
        raise InvalidRequestError("target_utilization must be a fraction in [0, 1), e.g. 0.10")

    target_balance = to_cents(account.credit_limit * target_utilization)
    payment = required_monthly_payment(account.balance, target_balance, account.annual_rate, months)
    return UtilizationPlan(
        account_id=account.id,
        credit_limit=account.credit_limit,
        current_balance=account.balance,
        current_utilization=to_ratio(account.balance / account.credit_limit),
        target_utilization=target_utilization,
        target_balance=target_balance,
        months=months,
        monthly_payment=payment,
        projection=project(profile, account_id, payment, months),
    )
