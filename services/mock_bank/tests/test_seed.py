from decimal import Decimal
from sqlalchemy import select, func
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.models import Customer, Account, Transaction
from app.seed import seed_database, LIABILITIES


def snapshot(app):
    with app.state.session_factory() as session:
        return ([tuple(getattr(c, k) for k in ("id", "email", "first_name", "created_at")) for c in session.scalars(select(Customer).order_by(Customer.id))],
                [tuple(getattr(a, k) for k in ("id", "balance", "apy", "credit_limit")) for a in session.scalars(select(Account).order_by(Account.id))],
                [tuple(getattr(t, k) for k in ("id", "amount", "transaction_date", "direction")) for t in session.scalars(select(Transaction).order_by(Transaction.id))])


def test_reproducibility_idempotency_restart(tmp_path):
    snapshots = []
    for i in range(2):
        app = create_app(Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / str(i)}.db"))
        with TestClient(app):
            before = snapshot(app)
            with app.state.session_factory() as session:
                seed_database(session, app.state.settings)
            assert snapshot(app) == before
            snapshots.append(before)
        with TestClient(app):
            assert snapshot(app) == before
    assert snapshots[0] == snapshots[1]


def test_all_banks_consistency_and_independence(tmp_path, authorize):
    for bank in ("chase", "amex", "pnc", "discover"):
        app = create_app(Settings(_env_file=None, bank_id=bank, bank_name=bank, data_seed=202,
                                  database_url=f"sqlite:///{tmp_path / bank}.db"))
        with TestClient(app) as client:
            assert client.get("/v1/institution").json()["id"] == bank
            with app.state.session_factory() as session:
                assert session.scalar(select(func.count()).select_from(Customer)) == 5
                assert session.connection().exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
                for account in session.scalars(select(Account)):
                    assert account.institution_id == bank
                    history = session.scalars(select(Transaction).where(Transaction.account_id == account.id)).all()
                    expected = account.opening_balance
                    for t in history:
                        sign = 1 if t.direction == "credit" else -1
                        if account.account_type in LIABILITIES:
                            sign *= -1
                        expected += sign*t.amount
                    assert expected == account.balance
                    if account.account_type in {"checking", "savings", "credit_card"}:
                        assert (max(t.transaction_date for t in history)-min(t.transaction_date for t in history)).days == 90
                    if account.credit_limit:
                        assert Decimal(0) <= account.balance <= account.credit_limit
                    if account.outstanding_principal:
                        assert account.outstanding_principal == account.balance
                for customer in session.scalars(select(Customer)):
                    assert session.scalar(select(func.count()).select_from(Account).where(Account.customer_id == customer.id)) >= 2


def test_database_bank_mismatch(tmp_path):
    import pytest
    url = f"sqlite:///{tmp_path / 'same.db'}"
    with TestClient(create_app(Settings(_env_file=None, database_url=url))):
        pass
    with pytest.raises(ValueError, match="another bank"):
        with TestClient(create_app(Settings(_env_file=None, database_url=url, bank_id="amex"))):
            pass
