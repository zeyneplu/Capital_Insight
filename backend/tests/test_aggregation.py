"""Contract integration against all six real mock ASGI apps; no network required."""
import asyncio
from contextlib import ExitStack
from datetime import timedelta
import logging
import re
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.models import Connection
from backend.app.database import utcnow
from services.mock_bank.app.main import create_app as create_bank
from services.mock_bank.app.config import Settings as BankSettings
from services.mock_loan.app.main import create_app as create_loan
from services.mock_loan.app.config import Settings as LoanSettings
from services.mock_mortgage.app.main import create_app as create_mortgage
from services.mock_mortgage.app.config import Settings as MortgageSettings


@pytest.fixture
def integrated(settings, tmp_path):
    with ExitStack() as stack:
        transports = {}
        for bank, seed in [("chase", 101), ("amex", 202), ("pnc", 303), ("discover", 404)]:
            app = create_bank(BankSettings(_env_file=None, bank_id=bank, bank_name=bank,
                database_url=f"sqlite:///{tmp_path / bank}.db", data_seed=seed, demo_mode=True))
            stack.enter_context(TestClient(app))
            transports[bank] = httpx.ASGITransport(app=app)
        for provider, factory, config in [("loans", create_loan, LoanSettings), ("mortgages", create_mortgage, MortgageSettings)]:
            app = factory(config(_env_file=None, database_url=f"sqlite:///{tmp_path / provider}.db", demo_mode=True))
            stack.enter_context(TestClient(app))
            transports[provider] = httpx.ASGITransport(app=app)
        down = set()
        async def send(request):
            if request.url.host in down:
                raise httpx.ConnectError("offline", request=request)
            return await transports[request.url.host].handle_async_request(request)
        upstream = httpx.AsyncClient(transport=httpx.MockTransport(send))
        settings.mock_service_urls = {provider: f"http://{provider}" for provider in transports}
        for provider, address in settings.mock_service_urls.items():
            setattr(settings, f"{provider}_url", address)
        client = stack.enter_context(TestClient(create_app(settings, http_client=upstream)))
        response = client.post("/v1/auth/register", json={"email": "alice@example.test", "password": "hackathon-2026"})
        from backend.app.models import User
        from backend.app.database import utcnow
        from sqlalchemy import select
        with client.app.state.session_factory() as database:
            for user in database.scalars(select(User)):
                user.email_verified_at = utcnow()
            database.commit()
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        yield client, headers, down
        asyncio.run(upstream.aclose())


def connect(client, headers, provider, caplog):
    email = f"customer1@{provider}.example.test"
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = client.post(f"/v1/connections/{provider}/request-code", json={"email": email}, headers=headers)
    assert response.status_code == 202, response.text
    code = re.search(r"DEVELOPMENT ONLY mock consent code for "+re.escape(email)+r": (\d{6})", caplog.text).group(1)
    response = client.post(f"/v1/connections/{provider}/verify-code", json={"email": email, "code": code}, headers=headers)
    assert response.status_code == 200, response.text
    assert "access_token" not in response.json() and "encrypted_token" not in response.json()
    return response.json()


def test_postings_work_through_both_core_interfaces(integrated,caplog):
    from decimal import Decimal
    from uuid import uuid4
    client,headers,_=integrated
    connect(client,headers,"chase",caplog)
    account=next(item for item in client.get("/v1/accounts",headers=headers).json()["items"] if item["account_type"]=="checking")
    before=Decimal(account["balance"])
    sid=client.post("/api/v1/sessions",headers=headers).json()["session_id"]
    for endpoint,auth in [(f"/v1/accounts/{account['id']}/transactions",headers),
        (f"/api/v1/accounts/{account['source_account_id']}/transactions",{**headers,"X-Session-Id":sid})]:
        body={"request_id":str(uuid4()),"operation":"salary","amount":"100.00","merchant":"Test employer"}
        result=client.post(endpoint,headers=auth,json=body)
        assert result.status_code==201,result.text
        assert result.json()["transactions"][0]["category"]=="salary"
        assert client.post(endpoint,headers=auth,json=body).json()["replayed"] is True
    after=next(item for item in client.get("/v1/accounts",headers=headers).json()["items"] if item["id"]==account["id"])
    assert Decimal(after["balance"])==before+Decimal("200")


def test_all_mock_services_portfolio_and_scoped_transactions(integrated, caplog):
    client, headers, _ = integrated
    connections = {provider: connect(client, headers, provider, caplog) for provider in ["chase", "amex", "pnc", "discover", "loans", "mortgages"]}
    assert len(client.get("/v1/connections", headers=headers).json()) == 6
    page = client.get("/v1/accounts", headers=headers).json()
    assert page["complete"] and not page["errors"]
    assert {item["provider"] for item in page["items"]} == {"chase", "amex", "pnc", "discover"}
    assert len({item["id"] for item in page["items"]}) == len(page["items"])
    assert all(isinstance(item["balance"], str) for item in page["items"])
    account = next(item for item in page["items"] if item["provider"] == "chase" and item["account_type"] == "checking")
    history = client.get(f"/v1/accounts/{account['id']}/transactions?limit=2&offset=1", headers=headers)
    assert history.status_code == 200, history.text
    assert len(history.json()["items"]) == 2
    assert history.json()["items"][0]["account_id"] == account["id"]
    loans = client.get("/v1/loans", headers=headers).json()
    mortgages = client.get("/v1/mortgages", headers=headers).json()
    assert len(loans["items"]) == 2 and len(mortgages["items"]) == 1
    assert all(item["current_balance"] is None for item in loans["items"]+mortgages["items"])
    summary = client.get("/v1/dashboard", headers=headers)
    assert summary.status_code == 200 and summary.json()["complete"]
    assert summary.json()["by_currency"][0]["currency"] == "USD"
    # Customer2's record through the same connection remains unavailable.
    other_id = connections["chase"]["id"]+":chase-customer-002-checking"
    assert client.get(f"/v1/accounts/{other_id}/transactions", headers=headers).status_code == 404


def test_provider_outage_reports_partial_data(integrated, caplog):
    client, headers, down = integrated
    connect(client, headers, "chase", caplog)
    connect(client, headers, "amex", caplog)
    down.add("amex")
    response = client.get("/v1/accounts", headers=headers)
    assert response.status_code == 200
    result = response.json()
    assert not result["complete"] and result["errors"][0]["provider"] == "amex"
    assert {item["provider"] for item in result["items"]} == {"chase"}


def test_expired_connection_and_upstream_validation(integrated, caplog):
    client, headers, _ = integrated
    connection = connect(client, headers, "chase", caplog)
    account_id = connection["id"]+":chase-customer-001-checking"
    for query in ("limit=0", "offset=-1", "start_date=2026-11-01&end_date=2026-01-01", "category=not-a-category"):
        assert client.get(f"/v1/accounts/{account_id}/transactions?{query}", headers=headers).status_code == 422
    with client.app.state.session_factory() as session:
        session.get(Connection, connection["id"]).expires_at = utcnow()-timedelta(seconds=1)
        session.commit()
    response = client.get("/v1/accounts", headers=headers).json()
    assert not response["complete"] and response["errors"][0]["status_code"] == 409


def test_application_proxy_and_schedule(integrated, caplog):
    client, headers, _ = integrated
    for provider, body in [("loans", {"loan_type": "personal_loan", "amount": "10000.00", "term_months": 36, "annual_income": "72000.00", "existing_monthly_debt": "300.00", "credit_score": 720}),
        ("mortgages", {"property_value": "350000.00", "down_payment": "70000.00", "term_months": 360, "annual_income": "120000.00", "existing_monthly_debt": "500.00", "credit_score": 740})]:
        connection = connect(client, headers, provider, caplog)
        base = f"/v1/connections/{connection['id']}"
        assert client.get(base+"/offers", headers=headers).status_code == 200
        response = client.post(base+"/applications", json=body, headers=headers)
        assert response.status_code == 201, response.text
        record = response.json()
        assert record["status"] == "approved"
        assert client.get(base+f"/records/{record['id']}/schedule", headers=headers).status_code == 200
        assert client.get(base+"/applications", headers=headers).status_code == 200


def test_core_health_cors_and_unlinked_user(client, auth_headers):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    assert "HTTPBearer" in client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert client.get("/v1/accounts", headers=auth_headers).json() == {"items": [], "errors": [], "complete": True}
    assert len(client.get("/v1/providers").json()) == 7
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET", "Access-Control-Request-Headers": "authorization"}
    assert client.options("/v1/accounts", headers=headers).headers["access-control-allow-origin"] == "http://localhost:3000"
    headers["Origin"] = "https://unknown.example"
    assert "access-control-allow-origin" not in client.options("/v1/accounts", headers=headers).headers
    assert client.post("/v1/connections/arbitrary-host/request-code", json={"email":"a@example.test"}, headers=auth_headers).status_code == 404
