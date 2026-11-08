"""Deterministic, append-nothing seed: existing bank data is never rewritten."""
import random
import secrets
from datetime import datetime, time, timezone, timedelta, date
from decimal import Decimal
from faker import Faker
from sqlalchemy import select
from .models import Customer, Account, Transaction, Metadata

PRODUCTS = {
    "chase": ["checking", "savings", "credit_card"],
    "amex": ["credit_card", "savings"],
    "pnc": ["checking", "savings", "cd", "personal_loan", "auto_loan", "mortgage", "ira"],
    "discover": ["credit_card", "personal_loan", "savings"],
}
LIABILITIES = {"credit_card", "personal_loan", "auto_loan", "mortgage"}
SPENDING = [("groceries", "Demo Market"), ("dining", "Fictional Cafe"), ("shopping", "Sample Store"),
            ("transportation", "Demo Transit"), ("utilities", "Example Energy"),
            ("entertainment", "Sample Cinema"), ("rent", "Fictional Housing"),
            ("healthcare", "Demo Clinic"), ("education", "Example Books"), ("other", "Sample Services")]


def seed_database(session, settings):
    existing = session.get(Metadata, "bank_id")
    if existing:
        if existing.value != settings.bank_id:
            raise ValueError("Database belongs to another bank; choose a separate file")
        return
    if session.scalar(select(Customer.id).limit(1)):
        raise ValueError("Refusing to seed an unrecognized nonempty database")
    rng = random.Random(settings.data_seed)
    fake = Faker("en_US")
    fake.seed_instance(settings.data_seed)
    stamp = datetime.combine(settings.seed_date, time(), timezone.utc)
    session.add_all([Metadata(key="bank_id", value=settings.bank_id),
                     Metadata(key="signing_secret", value=secrets.token_urlsafe(48))])
    for i in range(5):
        cid = f"{settings.bank_id}-customer-{i+1:03}"
        session.add(Customer(id=cid, first_name=fake.first_name(), last_name=fake.last_name(),
            email=f"customer{i+1}@{settings.bank_id}.example.test", date_of_birth=date(1980+i*3, 3, 12),
            synthetic_identity_id=f"SYNTH-{cid}", created_at=stamp))
        session.flush()
        for j, kind in enumerate(PRODUCTS.get(settings.bank_id, ["checking", "savings"])):
            aid = f"{cid}-{kind}"
            opening = Decimal(rng.randint(5000, 9000))
            if kind in LIABILITIES:
                opening = Decimal("1000") if kind == "credit_card" else Decimal("20000")
            account = Account(id=aid, customer_id=cid, institution_id=settings.bank_id,
                account_type=kind, account_name=f"{settings.bank_name} {kind.replace('_', ' ').title()}",
                account_number_last4=f"{rng.randrange(10000):04}", opening_balance=opening,
                balance=opening, created_at=stamp-timedelta(days=90), updated_at=stamp)
            if kind in {"checking", "savings", "cd"}:
                account.apy = Decimal(rng.randint(5, 450))/Decimal(10000)
            if kind == "credit_card":
                account.credit_limit = Decimal(rng.randint(5, 12)*1000)
                account.purchase_apr = Decimal(rng.randint(1700, 2900))/Decimal(10000)
                account.payment_due_date = settings.seed_date+timedelta(days=20)
            if kind in LIABILITIES-{"credit_card"}:
                account.original_principal = opening
                account.apr = Decimal(rng.randint(400, 1200))/Decimal(10000)
                account.monthly_payment = Decimal("300")
                account.term_months = 120
            if kind == "cd":
                account.maturity_date = settings.seed_date+timedelta(days=365)
            if kind == "ira":
                account.account_subtype = "roth"
                account.account_value = opening
            session.add(account)
            session.flush()
            balance = opening
            def entry(day, amount, direction, category, merchant):
                nonlocal balance
                txdate = settings.seed_date-timedelta(days=90-day)
                amount = Decimal(amount).quantize(Decimal("0.01"))
                sign = 1 if direction == "credit" else -1
                if kind in LIABILITIES:
                    sign *= -1
                balance += sign*amount
                session.add(Transaction(id=f"{aid}-tx-{day}-{category}", account_id=aid,
                    transaction_date=txdate, description=f"Synthetic {category}: {merchant}",
                    merchant=merchant, category=category, amount=amount, direction=direction,
                    transaction_type="payment" if category == "debt_payment" else "transfer" if category in {"salary", "transfers"} else "purchase",
                    created_at=datetime.combine(txdate, time(12), timezone.utc)))
            if kind in {"checking", "savings", "credit_card"}:
                for day in range(91):
                    if day % 30 == 0:
                        if kind == "checking":
                            entry(day, "3000", "credit", "salary", "Example Employer")
                        elif kind == "credit_card":
                            entry(day, min(balance, Decimal("900")), "credit", "debt_payment", "Demo Card Payment")
                        else:
                            entry(day, "250", "credit", "transfers", "Demo Savings Contribution")
                    if kind != "savings" or day % 10 == 0:
                        category, merchant = rng.choice(SPENDING)
                        entry(day, Decimal(rng.randint(500, 6000))/100, "debit", category, merchant)
            elif kind in LIABILITIES:
                for day in (0, 30, 60, 90):
                    entry(day, "300", "credit", "debt_payment", "Demo Principal Payment")
                account.outstanding_principal = balance
            account.balance = balance
            if kind == "credit_card":
                account.minimum_payment = max(Decimal("25"), balance*Decimal("0.02")).quantize(Decimal("0.01"))
                assert balance <= account.credit_limit
    session.commit()


def main():
    from .config import Settings
    from .database import Base, make_database
    settings = Settings()
    engine, factory = make_database(settings.database_url)
    Base.metadata.create_all(engine)
    with factory() as session:
        seed_database(session, settings)
    engine.dispose()
    print(f"Seed ready: {settings.bank_id}; demo email: customer1@{settings.bank_id}.example.test")


if __name__ == "__main__":
    main()
