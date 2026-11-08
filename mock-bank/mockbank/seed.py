"""Deterministic synthetic data.

Same (seed, bank_id, as_of date) -> byte-for-byte the same data. That is what lets
you run several replicas of one bank, or restart it, and get identical IDs and numbers.

Numbers come from code with a seeded random generator, never from an LLM: the LLM can't
guarantee that amounts add up, and every run would differ.
"""

import json
import random
import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from mockbank.models import Account, Customer, Transaction
from mockbank.validators import validate_ssn_last4

NAMESPACE = uuid.UUID("6f1c2a7e-3b5d-4c8e-9a10-2f4b6d8e0c11")

AccountType = Literal["checking", "savings", "credit_card", "loan", "mortgage", "cd", "ira"]

# (description, category, min $, max $) for everyday card/debit spending.
EVERYDAY = (
    ("Corner Grocery", "groceries", 18, 95),
    ("Campus Coffee", "dining", 4, 9),
    ("Burger Joint", "dining", 9, 24),
    ("Gas & Go", "transport", 28, 55),
    ("Big Box Store", "shopping", 12, 85),
    ("Cinema 8", "entertainment", 11, 28),
    ("RideShare", "transport", 9, 26),
)


# --- seed file schema (validated, so a typo fails loudly at startup) -------------


class SeedBill(BaseModel):
    """A recurring payment out of a checking account (rent, loan payments, card payments)."""

    description: str
    amount: Decimal
    day: int = Field(ge=1, le=28)
    category: str


class SeedAccount(BaseModel):
    type: AccountType
    nickname: str
    balance: Decimal
    annual_rate: Decimal = Decimal("0")
    credit_limit: Decimal | None = None
    monthly_income: Decimal | None = None  # checking: payroll deposits
    bills: list[SeedBill] = []  # checking: recurring payments out
    monthly_spend: Decimal | None = None  # credit card: purchases per month
    monthly_payment: Decimal | None = None  # loan / mortgage


class SeedCustomer(BaseModel):
    email: EmailStr
    full_name: str
    ssn_last4: Annotated[str, AfterValidator(validate_ssn_last4)]
    accounts: dict[str, list[SeedAccount]]  # bank_id -> accounts at that bank


class SeedFile(BaseModel):
    customers: list[SeedCustomer]


def load_seed_file(path: Path) -> SeedFile:
    return SeedFile.model_validate(json.loads(path.read_text()))


# --- generation --------------------------------------------------------------------


def to_cents(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def to_bps(rate: Decimal) -> int:
    return int((rate * 10_000).to_integral_value(rounding=ROUND_HALF_UP))


def _random_cents(rng: random.Random, low: float, high: float) -> int:
    return round(rng.uniform(low, high) * 100)


def _monthly_events(acct: SeedAccount, day: date, rng: random.Random) -> list[tuple[int, str, str]]:
    """Scheduled items for one day: (amount_cents, description, category)."""
    events: list[tuple[int, str, str]] = []
    monthly_interest = to_cents(acct.balance * acct.annual_rate / 12)

    if acct.type == "checking":
        if acct.monthly_income and day.day in (1, 15):
            events.append((to_cents(acct.monthly_income / 2), "Payroll - Acme Corp", "income"))
        for bill in acct.bills:
            if day.day == bill.day:
                events.append((-to_cents(bill.amount), bill.description, bill.category))
        if day.day == 8:
            events.append((-_random_cents(rng, 90, 160), "City Power & Water", "utilities"))
        if day.day == 12:
            events.append((-6500, "Mobile Phone Plan", "utilities"))
        if day.day == 18:
            events.append((-1599, "StreamFlix", "subscriptions"))
    elif acct.type == "savings" and day.day == 28 and monthly_interest:
        events.append((monthly_interest, "Interest earned", "interest"))
    elif acct.type == "credit_card":
        if acct.monthly_spend and day.day == 20:
            events.append((to_cents(acct.monthly_spend), "Payment - thank you", "payment"))
        if day.day == 27 and monthly_interest:
            events.append((-monthly_interest, "Interest charge", "fees"))
    elif acct.type in ("loan", "mortgage") and acct.monthly_payment and day.day == 5:
        events.append((to_cents(acct.monthly_payment), "Payment received", "payment"))
    elif acct.type in ("cd", "ira") and day.day == 28 and monthly_interest:
        events.append((monthly_interest, "Interest earned", "interest"))
    return events


def _everyday_purchases(acct: SeedAccount, rng: random.Random) -> list[tuple[int, str, str]]:
    """Random debit/card purchases for one day."""
    if acct.type == "checking":
        expected = 0.30  # about one debit purchase every 3 days
    elif acct.type == "credit_card" and acct.monthly_spend:
        # Expected purchases per day so the month adds up to roughly monthly_spend.
        avg_purchase = sum((lo + hi) / 2 for _, _, lo, hi in EVERYDAY) / len(EVERYDAY)
        expected = float(acct.monthly_spend) / 30 / avg_purchase
    else:
        return []
    count = int(expected) + (rng.random() < expected % 1)
    purchases = []
    for _ in range(count):
        desc, category, lo, hi = rng.choice(EVERYDAY)
        purchases.append((-_random_cents(rng, lo, hi), desc, category))
    return purchases


def seed_bank(
    session: Session,
    seed_file: SeedFile,
    *,
    bank_id: str,
    seed: int,
    history_days: int,
    as_of: date,
) -> None:
    start = as_of - timedelta(days=history_days - 1)

    for person in seed_file.customers:
        accounts = person.accounts.get(bank_id)
        if not accounts:
            continue  # this person doesn't bank here
        email = person.email.lower()
        customer_id = str(uuid.uuid5(NAMESPACE, f"{bank_id}:{email}"))
        session.add(
            Customer(
                id=customer_id,
                email=email,
                full_name=person.full_name,
                ssn_last4=person.ssn_last4,
            )
        )

        for index, acct in enumerate(accounts):
            rng = random.Random(f"{seed}:{bank_id}:{email}:{index}")
            account_id = str(uuid.uuid5(NAMESPACE, f"{bank_id}:{email}:{index}"))
            session.add(
                Account(
                    id=account_id,
                    customer_id=customer_id,
                    type=acct.type,
                    nickname=acct.nickname,
                    mask=f"{rng.randrange(10_000):04d}",
                    balance_cents=to_cents(acct.balance),
                    rate_bps=to_bps(acct.annual_rate),
                    credit_limit_cents=to_cents(acct.credit_limit) if acct.credit_limit else None,
                )
            )

            n = 0
            for offset in range(history_days):
                day = start + timedelta(days=offset)
                todays = _monthly_events(acct, day, rng) + _everyday_purchases(acct, rng)
                for amount, desc, category in todays:
                    session.add(
                        Transaction(
                            id=str(uuid.uuid5(NAMESPACE, f"{account_id}:{n}")),
                            account_id=account_id,
                            posted_on=day,
                            amount_cents=amount,
                            description=desc,
                            category=category,
                        )
                    )
                    n += 1
    session.commit()
