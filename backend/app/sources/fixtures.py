"""Synthetic demo personas.

Rules for demo data (from our "trust/security" brainstorm):
- Fully fictional people. No SSNs, not even fake ones: we never need them, so we never
  store them (data minimization). Judges notice this.
- Every persona tells a story the demo can walk through.
"""

from datetime import date
from decimal import Decimal

from app.domain.errors import NotFoundError
from app.domain.models import Account, AccountType, FinancialProfile, Transaction

# Persona "Alex": the numbers from our whiteboard sketch.
#   PNC credit line $2,500 at 18% APR, $600 owed  -> 24% utilization
#   Savings $5,000 at 5% yield, checking $1,700 at 0%
#   Goal: "How do I increase my credit score?"
ALEX = FinancialProfile(
    customer_id="demo-alex",
    display_name="Alex Rivera",
    monthly_income=Decimal("3200.00"),
    monthly_expenses=Decimal("1500.00"),
    accounts=(
        Account(
            id="pnc-cc-1",
            institution="PNC",
            type=AccountType.CREDIT_CARD,
            nickname="PNC Cash Rewards Visa",
            balance=Decimal("600.00"),
            annual_rate=Decimal("0.18"),
            credit_limit=Decimal("2500.00"),
        ),
        Account(
            id="pnc-sav-1",
            institution="PNC",
            type=AccountType.SAVINGS,
            nickname="High-Yield Savings",
            balance=Decimal("5000.00"),
            annual_rate=Decimal("0.05"),
        ),
        Account(
            id="c1-chk-1",
            institution="Capital One",
            type=AccountType.CHECKING,
            nickname="360 Checking",
            balance=Decimal("1700.00"),
            annual_rate=Decimal("0"),
        ),
    ),
)


def _tx(n: int, account: str, day: str, amount: str, desc: str, category: str) -> Transaction:
    return Transaction(
        id=f"fx-{n}",
        account_id=account,
        posted_on=date.fromisoformat(day),
        amount=Decimal(amount),
        description=desc,
        category=category,
    )


# One month of Alex's activity (October 2026), newest first.
ALEX_TRANSACTIONS = [
    _tx(1, "pnc-cc-1", "2026-10-27", "-9.00", "Interest charge", "fees"),
    _tx(2, "pnc-cc-1", "2026-10-24", "-62.40", "Corner Grocery", "groceries"),
    _tx(3, "c1-chk-1", "2026-10-20", "-450.00", "PNC card payment", "transfer"),
    _tx(4, "pnc-cc-1", "2026-10-20", "450.00", "Payment - thank you", "payment"),
    _tx(5, "pnc-cc-1", "2026-10-18", "-38.75", "Burger Joint", "dining"),
    _tx(6, "c1-chk-1", "2026-10-18", "-15.99", "StreamFlix", "subscriptions"),
    _tx(7, "c1-chk-1", "2026-10-15", "1600.00", "Payroll - Acme Corp", "income"),
    _tx(8, "pnc-cc-1", "2026-10-12", "-48.10", "Gas & Go", "transport"),
    _tx(9, "c1-chk-1", "2026-10-08", "-124.30", "City Power & Water", "utilities"),
    _tx(10, "pnc-cc-1", "2026-10-06", "-91.25", "Big Box Store", "shopping"),
    _tx(11, "c1-chk-1", "2026-10-01", "-1100.00", "Rent - Parkside Apartments", "housing"),
    _tx(12, "c1-chk-1", "2026-10-01", "1600.00", "Payroll - Acme Corp", "income"),
]

PERSONAS: dict[str, FinancialProfile] = {p.customer_id: p for p in (ALEX,)}
TRANSACTIONS: dict[str, list[Transaction]] = {ALEX.customer_id: ALEX_TRANSACTIONS}


class FixtureSource:
    """In-memory source. Default in dev and tests: fast, offline, deterministic."""

    def __init__(self, personas: dict[str, FinancialProfile] | None = None) -> None:
        self._personas = PERSONAS if personas is None else personas

    async def get_profile(self, customer_id: str) -> FinancialProfile:
        try:
            return self._personas[customer_id]
        except KeyError:
            raise NotFoundError(f"Customer {customer_id!r} not found") from None

    async def get_transactions(self, customer_id: str) -> list[Transaction]:
        await self.get_profile(customer_id)  # same 404 behavior as the profile
        return list(TRANSACTIONS.get(customer_id, []))
