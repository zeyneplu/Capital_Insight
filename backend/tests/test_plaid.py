"""Plaid contract checks use only HTTPX MockTransport, never real credentials."""

import asyncio
import json

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.models import CachedTransaction, Connection, PlaidState


class PlaidStub:
    def __init__(self):
        self.requests = []
        self.sync_pages = []
        self.account_response = {
            "accounts": [{"account_id": "checking-1", "type": "depository", "subtype": "checking",
                          "name": "Demo checking", "balances": {"current": 1250.25, "iso_currency_code": "USD"}}],
        }
        self.account_status = 200

    def __call__(self, request):
        payload = json.loads(request.content)
        self.requests.append((request.url.path, payload))
        path = request.url.path
        if path == "/link/token/create":
            return httpx.Response(200, json={"link_token": "link-sandbox-test", "expiration": "2026-11-08T10:00:00Z"})
        if path == "/sandbox/public_token/create":
            return httpx.Response(200, json={"public_token": "public-sandbox-test"})
        if path == "/item/public_token/exchange":
            return httpx.Response(200, json={"access_token": "access-sandbox-secret", "item_id": "item-1"})
        if path == "/accounts/get":
            if isinstance(self.account_response, str):
                return httpx.Response(self.account_status, content=self.account_response)
            return httpx.Response(self.account_status, json=self.account_response)
        if path == "/transactions/sync":
            assert self.sync_pages, "Unexpected extra sync request"
            response = self.sync_pages.pop(0)
            return response if isinstance(response, httpx.Response) else httpx.Response(200, json=response)
        raise AssertionError(f"Unexpected Plaid request: {path}")


@pytest.fixture
def plaid_context():
    stub = PlaidStub()
    settings = Settings(
        _env_file=None,
        database_url="sqlite:///:memory:",
        encryption_key=Fernet.generate_key().decode(),
        plaid_client_id="test-client-id",
        plaid_secret="test-plaid-secret",
    )
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(stub))
    app = create_app(settings, upstream)
    with TestClient(app) as client:
        registration = client.post("/v1/auth/register", json={"email": "plaid@example.test", "password": "fictional-password"})
        assert registration.status_code == 201
        from backend.app.models import User
        from backend.app.database import utcnow
        from sqlalchemy import select
        with client.app.state.session_factory() as database:
            for user in database.scalars(select(User)):
                user.email_verified_at = utcnow()
            database.commit()
        headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
        yield app, client, headers, stub
    asyncio.run(upstream.aclose())


def connect(client, headers):
    result = client.post("/v1/plaid/exchange-public-token", headers=headers, json={"public_token": "public-sandbox-test"})
    assert result.status_code == 201, result.text
    return result.json()["id"]


def transaction(transaction_id, amount=12.25, account_id="checking-1", day="2026-11-01"):
    return {"transaction_id": transaction_id, "account_id": account_id, "date": day,
            "name": "Synthetic merchant", "amount": amount, "iso_currency_code": "USD", "pending": False}


def page(cursor, added=None, modified=None, removed=None, more=False):
    return {"added": added or [], "modified": modified or [], "removed": removed or [],
            "next_cursor": cursor, "has_more": more}


def set_cursor(app, connection_id, cursor):
    with app.state.session_factory() as session:
        session.get(PlaidState, connection_id).cursor = cursor
        session.commit()


def test_link_requires_application_login_and_uses_internal_user_id(plaid_context):
    app, client, headers, stub = plaid_context
    assert client.post("/v1/plaid/link-token").status_code == 401
    response = client.post("/v1/plaid/link-token", headers=headers)
    assert response.status_code == 200
    assert response.json()["link_token"] == "link-sandbox-test"
    payload = stub.requests[-1][1]
    assert "@" not in payload["user"]["client_user_id"]
    assert payload["products"] == ["transactions"]
    assert payload["client_id"] == "test-client-id"
    assert payload["secret"] == "test-plaid-secret"
    assert "secret" not in response.text


def test_unconfigured_plaid_fails_without_network(plaid_context):
    app, client, headers, stub = plaid_context
    app.state.settings.plaid_secret = None
    response = client.post("/v1/plaid/link-token", headers=headers)
    assert response.status_code == 503
    assert stub.requests == []


def test_sandbox_api_only_token_is_disabled_in_production(plaid_context):
    app, client, headers, stub = plaid_context
    response = client.post("/v1/plaid/sandbox/public-token", headers=headers, json={})
    assert response.status_code == 200
    assert response.json() == {"public_token": "public-sandbox-test"}
    assert stub.requests[-1][1]["initial_products"] == ["transactions"]
    app.state.settings.plaid_environment = "production"
    assert client.post("/v1/plaid/sandbox/public-token", headers=headers, json={}).status_code == 404


def test_exchange_encrypts_access_token_and_never_returns_it(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    with app.state.session_factory() as session:
        connection = session.get(Connection, connection_id)
        assert connection.encrypted_token != "access-sandbox-secret"
        assert app.state.cipher.decrypt(connection.encrypted_token.encode()).decode() == "access-sandbox-secret"
        assert session.get(PlaidState, connection_id).cursor is None
    response = client.get("/v1/connections", headers=headers)
    assert "access-sandbox-secret" not in response.text
    assert "encrypted_token" not in response.text


def test_accounts_preserve_decimal_precision_nulls_and_debt_semantics(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    stub.account_response = '''{"accounts":[
      {"account_id":"asset","type":"depository","subtype":"checking","name":"Checking",
       "balances":{"current":123.123456789012345678,"iso_currency_code":"USD"}},
      {"account_id":"debt","type":"credit","subtype":"credit card","name":"Card",
       "balances":{"current":42.25,"iso_currency_code":"USD"}},
      {"account_id":"unknown","type":"other","name":"Unknown","balances":{"current":null}}
    ]}'''
    response = client.get(f"/v1/plaid/connections/{connection_id}/accounts", headers=headers)
    assert response.status_code == 200
    asset, debt, unknown = response.json()
    assert asset["id"] == f"{connection_id}:asset"
    assert asset["balance"] == "123.123456789012345678"
    assert asset["balance_kind"] == "asset"
    assert debt["balance_kind"] == "liability"
    assert debt["account_type"] == "credit_card"
    assert unknown["balance"] is None
    assert unknown["currency"] is None
    assert unknown["balance_kind"] == "unknown"


def test_sync_paginates_and_applies_added_modified_removed_atomically(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    stub.sync_pages = [
        page("first-page", added=[transaction("t1"), transaction("t2")], more=True),
        page("final-page", modified=[transaction("t1", amount=-100.15)], removed=[{"transaction_id": "t2"}]),
    ]
    response = client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json() == {"added": 2, "modified": 1, "removed": 1}
    assert [payload.get("cursor") for path, payload in stub.requests if path == "/transactions/sync"] == [None, "first-page"]
    listing = client.get(f"/v1/plaid/connections/{connection_id}/transactions", headers=headers).json()
    assert listing["total"] == 1
    assert listing["items"][0]["amount"] == "100.15"
    assert listing["items"][0]["direction"] == "credit"
    assert listing["items"][0]["account_id"] == f"{connection_id}:checking-1"
    with app.state.session_factory() as session:
        assert session.get(PlaidState, connection_id).cursor == "final-page"


def test_failed_later_page_preserves_previous_cursor_and_cache(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    set_cursor(app, connection_id, "original-cursor")
    stub.sync_pages = [
        page("partial-cursor", added=[transaction("partial")], more=True),
        httpx.Response(400, json={"error_code": "PRODUCT_NOT_READY", "request_id": "request-123",
                                 "error_message": "private access-sandbox-secret"}),
    ]
    response = client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=headers)
    assert response.status_code == 502
    assert "access-sandbox-secret" not in response.text
    assert response.json()["detail"]["request_id"] == "request-123"
    with app.state.session_factory() as session:
        assert session.get(PlaidState, connection_id).cursor == "original-cursor"
        assert session.scalars(select(CachedTransaction)).all() == []


def test_pagination_mutation_restarts_from_original_cursor(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    set_cursor(app, connection_id, "original-cursor")
    stub.sync_pages = [
        page("abandoned-cursor", added=[transaction("abandoned")], more=True),
        httpx.Response(400, json={"error_code": "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION"}),
        page("committed-cursor", added=[transaction("committed")]),
    ]
    response = client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"added": 1, "modified": 0, "removed": 0}
    assert [payload.get("cursor") for path, payload in stub.requests if path == "/transactions/sync"] == [
        "original-cursor", "abandoned-cursor", "original-cursor",
    ]
    with app.state.session_factory() as session:
        assert [row.remote_id for row in session.scalars(select(CachedTransaction))] == ["committed"]
        assert session.get(PlaidState, connection_id).cursor == "committed-cursor"


def test_concurrent_cursor_advance_cannot_overwrite_another_import(plaid_context, monkeypatch):
    from backend.app import plaid

    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    set_cursor(app, connection_id, "original-cursor")

    async def competing_import(*args):
        # Simulate another worker committing while this worker waits for Plaid.
        with app.state.session_factory() as session:
            session.get(PlaidState, connection_id).cursor = "other-worker-cursor"
            session.add(CachedTransaction(
                connection_id=connection_id, remote_id="other-worker-record",
                payload=plaid.normalize_transaction(connection_id, transaction("other-worker-record")),
            ))
            session.commit()
        return [page("stale-cursor", added=[transaction("stale-record")])], "stale-cursor"

    monkeypatch.setattr(plaid, "_collect_updates", competing_import)
    response = client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=headers)
    assert response.status_code == 409
    with app.state.session_factory() as session:
        assert session.get(PlaidState, connection_id).cursor == "other-worker-cursor"
        assert [row.remote_id for row in session.scalars(select(CachedTransaction))] == ["other-worker-record"]


def test_repeated_pagination_mutation_stops_after_three_attempts(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    stub.sync_pages = [httpx.Response(400, json={
        "error_code": "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION",
    }) for _ in range(3)]
    response = client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=headers)
    assert response.status_code == 502
    assert len([path for path, _ in stub.requests if path == "/transactions/sync"]) == 3
    with app.state.session_factory() as session:
        assert session.get(PlaidState, connection_id).cursor is None


def test_malformed_later_page_never_partially_imports(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    stub.sync_pages = [page("first", added=[transaction("valid")], more=True),
                       page("last", added=[{"transaction_id": "invalid"}])]
    response = client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=headers)
    assert response.status_code == 502
    with app.state.session_factory() as session:
        assert session.get(PlaidState, connection_id).cursor is None
        assert session.scalars(select(CachedTransaction)).all() == []


def test_incremental_sync_updates_existing_and_filters_cached_transactions(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    url = f"/v1/plaid/connections/{connection_id}"
    stub.sync_pages = [page("cursor-1", added=[transaction("t1"), transaction("t2", account_id="savings-2")])]
    assert client.post(f"{url}/sync", headers=headers).status_code == 200
    stub.sync_pages = [page("cursor-2", modified=[transaction("t1", amount=99.99)], added=[transaction("t3", day="2026-11-02")])]
    assert client.post(f"{url}/sync", headers=headers).status_code == 200
    result = client.get(f"{url}/transactions", headers=headers, params={"account_id": f"{connection_id}:checking-1", "limit": 1, "offset": 1}).json()
    assert result["total"] == 2
    assert result["items"][0]["source_transaction_id"] == "t1"
    assert result["items"][0]["amount"] == "99.99"
    assert client.get(f"{url}/transactions?limit=101", headers=headers).status_code == 422


def test_connections_are_scoped_to_owner_for_all_plaid_endpoints(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    registration = client.post("/v1/auth/register", json={"email": "other-plaid@example.test", "password": "fictional-password"})
    from backend.app.models import User
    from backend.app.database import utcnow
    with app.state.session_factory() as database:
        database.scalar(select(User).where(User.email == "other-plaid@example.test")).email_verified_at=utcnow()
        database.commit()
    other_headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
    for route in ("accounts", "transactions"):
        assert client.get(f"/v1/plaid/connections/{connection_id}/{route}", headers=other_headers).status_code == 404
    assert client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=other_headers).status_code == 404
    assert client.post("/v1/plaid/link-token", headers=other_headers, json={"connection_id": connection_id}).status_code == 404
    assert len(stub.requests) == 1


def test_login_required_is_actionable_and_does_not_leak_provider_message(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    stub.account_status = 400
    stub.account_response = {"error_code": "ITEM_LOGIN_REQUIRED", "request_id": "req-login",
                             "error_message": "sensitive account details"}
    response = client.get(f"/v1/plaid/connections/{connection_id}/accounts", headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["action"]
    assert "sensitive" not in response.text


def test_update_mode_keeps_access_token_on_server(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    response = client.post("/v1/plaid/link-token", headers=headers, json={"connection_id": connection_id})
    assert response.status_code == 200
    payload = stub.requests[-1][1]
    assert payload["access_token"] == "access-sandbox-secret"
    assert "products" not in payload
    assert "access-sandbox-secret" not in response.text


def test_repeated_exchange_updates_item_without_losing_sync_cursor(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    set_cursor(app, connection_id, "previous-import")
    assert connect(client, headers) == connection_id
    with app.state.session_factory() as session:
        assert len(session.scalars(select(Connection)).all()) == 1
        assert session.get(PlaidState, connection_id).cursor == "previous-import"


def test_non_plaid_connection_is_not_accepted(plaid_context):
    app, client, headers, stub = plaid_context
    connection_id = connect(client, headers)
    with app.state.session_factory() as session:
        connection = session.get(Connection, connection_id)
        connection.kind = "mock_bank"
        connection.provider = "chase"
        session.commit()
    for route in ("accounts", "transactions"):
        assert client.get(f"/v1/plaid/connections/{connection_id}/{route}", headers=headers).status_code == 404
    assert client.post(f"/v1/plaid/connections/{connection_id}/sync", headers=headers).status_code == 404
    assert len(stub.requests) == 1
