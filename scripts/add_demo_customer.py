"""Add an email to the seven local development databases without bypassing verification.

Run from the repository root: python scripts/add_demo_customer.py --email you@example.com
Start the stack once first so its databases contain the standard synthetic seeds.
Existing customers and financial records are never replaced. No email is sent.
"""

import argparse
from datetime import date
from hashlib import sha256
import importlib
from pathlib import Path
import re
import sys

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def normalize_email(value):
    email = value.strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", email):
        raise ValueError("Enter one valid email address")
    return email


def clone(row, **changes):
    values = {column.key: getattr(row, column.key) for column in row.__table__.columns}
    return type(row)(**(values | changes))


def provision_mock(session, models, provider, email, record_model):
    """Copy only seeded financial data, with new IDs and ownership; reruns are no-ops."""
    existing = session.scalar(select(models.Customer).where(models.Customer.email == email))
    if existing:
        count = len(session.scalars(select(record_model).where(record_model.customer_id == existing.id)).all())
        return {"status": "already exists", "records": count}

    template = session.scalar(select(models.Customer).where(
        models.Customer.email == f"customer1@{provider}.example.test"))
    if template is None:
        raise ValueError(f"{provider}: standard synthetic seed is missing; start the service first")
    records = session.scalars(select(record_model).where(record_model.customer_id == template.id)).all()
    if not records:
        raise ValueError(f"{provider}: seed customer has no synthetic financial records")

    customer_id = f"{provider}-demo-{sha256(email.encode()).hexdigest()[:20]}"
    session.add(models.Customer(
        id=customer_id, first_name="Demo", last_name="Customer", email=email,
        date_of_birth=date(1990, 1, 1), synthetic_identity_id=f"SYNTH-{customer_id}",
    ))
    session.flush()
    transactions = 0
    for index, record in enumerate(records, 1):
        record_id = f"{customer_id}-record-{index}"
        changes = {"id":record_id, "customer_id":customer_id}
        if hasattr(record, "credit_score"):
            # Newly provisioned fictional applications start with this customer's score.
            from services.mock_bank.app.credit import synthetic_credit_score
            changes["credit_score"] = synthetic_credit_score(email)
        session.add(clone(record, **changes))
        session.flush()
        if hasattr(models, "Transaction"):
            for number, transaction in enumerate(session.scalars(select(models.Transaction).where(
                models.Transaction.account_id == record.id)), 1):
                session.add(clone(transaction, id=f"{record_id}-tx-{number}", account_id=record_id))
                transactions += 1
    session.commit()
    return {"status": "created", "records": len(records), "transactions": transactions}


def provision_core(session, email):
    from backend.app.models import User
    user = session.scalar(select(User).where(User.email == email))
    if user:
        return {"status": "already exists", "verified": user.email_verified_at is not None}
    session.add(User(email=email, password_hash="!email-only"))
    session.commit()
    return {"status": "created", "verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    try:
        email = normalize_email(args.email)
    except ValueError as error:
        parser.error(str(error))

    targets = [
        ("chase", "mock_bank", "Account"), ("amex", "mock_bank", "Account"),
        ("pnc", "mock_bank", "Account"), ("discover", "mock_bank", "Account"),
        ("loans", "mock_loan", "LoanApplication"),
        ("mortgages", "mock_mortgage", "MortgageApplication"),
    ]
    for provider, service, _ in targets:
        path = ROOT / "services" / service / "data" / f"{provider}.db"
        if not path.is_file():
            parser.error(f"Missing {provider} database. Start the local services first.")

    for provider, service, model_name in targets:
        database = importlib.import_module(f"services.{service}.app.database")
        models = importlib.import_module(f"services.{service}.app.models")
        path = ROOT / "services" / service / "data" / f"{provider}.db"
        engine, factory = database.make_database(f"sqlite:///{path.as_posix()}")
        try:
            importlib.import_module(f"services.{service}.app.credit").upgrade_credit_schema(engine)
            with factory() as session:
                result = provision_mock(session, models, provider, email, getattr(models, model_name))
                print(f"{provider}: {result}")
        finally:
            engine.dispose()

    from backend.app.config import Settings
    from backend.app.database import make_database
    engine, factory = make_database(Settings().database_url)
    try:
        with factory() as session:
            print(f"core: {provision_core(session, email)}")
    finally:
        engine.dispose()
    print(f"Ready: {email}. Sign in and verify your inbox, then use this email at each mock institution.")


if __name__ == "__main__":
    main()
