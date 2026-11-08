"""Provisioning preserves seed ownership, financial data, and verification."""
import importlib

import pytest
from sqlalchemy import func, select

from scripts.add_demo_customer import normalize_email, provision_core, provision_mock


@pytest.mark.parametrize("provider,service,model_name,seed_name", [
    ("chase", "mock_bank", "Account", "seed_database"),
    ("amex", "mock_bank", "Account", "seed_database"),
    ("pnc", "mock_bank", "Account", "seed_database"),
    ("discover", "mock_bank", "Account", "seed_database"),
    ("loans", "mock_loan", "LoanApplication", "seed_loans"),
    ("mortgages", "mock_mortgage", "MortgageApplication", "seed_mortgages"),
])
def test_provision_mock_is_additive_and_idempotent(tmp_path, provider, service, model_name, seed_name):
    prefix = f"services.{service}.app"
    database = importlib.import_module(f"{prefix}.database")
    models = importlib.import_module(f"{prefix}.models")
    config = importlib.import_module(f"{prefix}.config")
    seed = getattr(importlib.import_module(f"{prefix}.seed"), seed_name)
    identity = {"bank_id" if service == "mock_bank" else "lender_id": provider}
    settings = config.Settings(_env_file=None, **identity)
    engine, factory = database.make_database(f"sqlite:///{tmp_path / 'test.db'}")
    database.Base.metadata.create_all(engine)
    record_model = getattr(models, model_name)
    with factory() as session:
        seed(session, settings)
        original_count = session.scalar(select(func.count()).select_from(record_model))
        result = provision_mock(session, models, provider, "tester@example.com", record_model)
        assert result["status"] == "created"
        assert result["records"] > 0
        customer = session.scalar(select(models.Customer).where(models.Customer.email == "tester@example.com"))
        assert customer.synthetic_identity_id.startswith("SYNTH-")
        assert session.scalar(select(func.count()).select_from(models.Customer)) == 6
        count = session.scalar(select(func.count()).select_from(record_model))
        assert count == original_count + result["records"]
        assert provision_mock(session, models, provider, customer.email, record_model)["status"] == "already exists"
        assert session.scalar(select(func.count()).select_from(record_model)) == count
        if service == "mock_bank":
            accounts = session.scalars(select(models.Account).where(models.Account.customer_id == customer.id)).all()
            for account in accounts:
                transactions = session.scalars(select(models.Transaction).where(models.Transaction.account_id == account.id)).all()
                delta = sum(tx.amount if tx.direction == "credit" else -tx.amount for tx in transactions)
                if account.account_type in {"credit_card", "personal_loan", "auto_loan", "mortgage"}:
                    delta = -delta
                assert account.opening_balance + delta == account.balance
    engine.dispose()


def test_core_provision_requires_verification_and_preserves_existing_user(client):
    from backend.app.models import User
    from backend.app.database import utcnow
    with client.app.state.session_factory() as session:
        assert provision_core(session, "tester@example.com") == {"status": "created", "verified": False}
        user = session.scalar(select(User).where(User.email == "tester@example.com"))
        assert user.password_hash == "!email-only"
        user.email_verified_at = utcnow()
        session.commit()
        original_id = user.id
        assert provision_core(session, user.email) == {"status": "already exists", "verified": True}
        assert session.scalar(select(User).where(User.email == user.email)).id == original_id


def test_email_normalization():
    assert normalize_email(" Tester@Example.com ") == "tester@example.com"
    with pytest.raises(ValueError):
        normalize_email("one@example.com,two@example.com")
