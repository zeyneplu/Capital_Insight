from datetime import timedelta
import importlib

import httpx
import pytest
from sqlalchemy import create_engine, select, text, func

from backend.app.database import utcnow
from backend.app.models import Connection, CreditProfile, User


@pytest.mark.parametrize("service", ["mock_bank", "mock_loan", "mock_mortgage"])
def test_current_score_upgrade_is_consistent_and_preserves_historical_scores(tmp_path, service):
    credit = importlib.import_module(f"services.{service}.app.credit")
    from services.mock_bank.app.credit import synthetic_credit_score
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE customers (id TEXT PRIMARY KEY, email TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO customers VALUES ('a',' Alice@Example.test ')"))
        connection.execute(text("CREATE TABLE historical_application (credit_score INTEGER)"))
        connection.execute(text("INSERT INTO historical_application VALUES (610)"))
    credit.upgrade_credit_schema(engine)
    credit.upgrade_credit_schema(engine)
    with engine.connect() as connection:
        row = connection.execute(text("SELECT credit_score, credit_score_as_of FROM customers")).one()
        assert row.credit_score == synthetic_credit_score("alice@example.test")
        assert 300 <= row.credit_score <= 850 and row.credit_score_as_of
        assert connection.scalar(text("SELECT credit_score FROM historical_application")) == 610
    assert credit.synthetic_credit_score("alice@example.test") == credit.synthetic_credit_score(" ALICE@example.test ")
    engine.dispose()


@pytest.fixture
def bank_reports(client, auth_headers, monkeypatch):
    state = {8001:740, 8002:740}
    async def send(method, url, **kwargs):
        score = state.get(httpx.URL(url).port)
        if score is None:
            return httpx.Response(503, json={"detail":"unavailable"})
        assert kwargs["headers"]["Authorization"].startswith("Bearer ")
        return httpx.Response(200, json={"id":"mock-customer", "email":"alice@example.test",
            "credit_score":score, "credit_score_as_of":"2026-11-08"})
    monkeypatch.setattr(client.app.state.http_client, "request", send)
    return state


def add_link(client, provider="chase", kind="mock_bank", expired=False):
    with client.app.state.session_factory() as session:
        user = session.scalar(select(User))
        link = Connection(user_id=user.id, provider=provider, kind=kind, remote_id=provider,
            display_name=provider.title(), encrypted_token=client.app.state.cipher.encrypt(b"consent-token").decode(),
            expires_at=utcnow()+timedelta(hours=-1 if expired else 1))
        session.add(link)
        session.commit()


def test_credit_requires_verified_login(client):
    assert client.get("/v1/credit-score").status_code == 401
    token = client.post("/v1/auth/register",json={"email":"unverified@example.test","password":"example-password"}).json()["access_token"]
    assert client.get("/v1/credit-score",headers={"Authorization":"Bearer "+token}).status_code == 403


def test_multiple_banks_return_one_current_score_and_one_profile(client, auth_headers, bank_reports):
    add_link(client)
    add_link(client, "amex")
    for _ in range(2):
        response = client.get("/v1/credit-score",headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["score"] == 740
        assert response.json()["sources"] == ["Amex", "Chase"]
        assert response.json()["synthetic"] is True
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CreditProfile)) == 1
        assert all(link.customer_profile["credit_score"] == 740 for link in session.scalars(select(Connection)))


def test_conflicting_profiles_are_not_averaged_or_silently_chosen(client, auth_headers, bank_reports):
    add_link(client)
    add_link(client,"amex")
    bank_reports[8002] = 700
    data = client.get("/v1/credit-score",headers=auth_headers).json()
    assert data["score"] is None and data["status"] == "conflicting_profiles"


def test_nonbank_and_expired_consents_do_not_expose_scores(client, auth_headers, bank_reports):
    add_link(client,"plaid","plaid")
    add_link(client,"loans","mock_loan")
    add_link(client,expired=True)
    data = client.get("/v1/credit-score",headers=auth_headers).json()
    assert data["score"] is None and data["status"] == "connect_bank"


def test_provider_failure_does_not_invent_scores_or_hide_healthy_report(client, auth_headers, bank_reports):
    add_link(client)
    add_link(client,"amex")
    bank_reports[8002] = None
    data = client.get("/v1/credit-score",headers=auth_headers).json()
    assert data["score"] == 740 and data["sources"] == ["Chase"]
    bank_reports[8001] = None
    data = client.get("/v1/credit-score",headers=auth_headers).json()
    assert data["score"] is None and data["status"] == "unavailable"


def test_score_not_shared_between_app_users(client, auth_headers, bank_reports):
    add_link(client)
    assert client.get("/v1/credit-score",headers=auth_headers).json()["score"] == 740
    response = client.post("/v1/auth/register",json={"email":"second@example.test","password":"another-password"}).json()
    with client.app.state.session_factory() as session:
        session.scalar(select(User).where(User.email=="second@example.test")).email_verified_at=utcnow()
        session.commit()
    data = client.get("/v1/credit-score",headers={"Authorization":"Bearer "+response["access_token"]}).json()
    assert data["score"] is None and data["status"] == "connect_bank"
