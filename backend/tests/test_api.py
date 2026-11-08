"""API tests against a fake upstream (httpx.MockTransport): no services needed."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

CODE = "123456"
ACCOUNTS = {
    "chase": [{"id": "chase-customer-001-checking", "institution_id": "chase", "balance": "100.00"}],
    "amex": [{"id": "amex-customer-001-credit_card", "institution_id": "amex", "balance": "50.00"}],
}
TX = [{"id": f"tx-{i}", "amount": "1.00"} for i in range(150)]


class FakeServices:
    """Minimal stand-ins for mock_bank / mock_loan, keyed by host."""

    def __init__(self):
        self.revoked: set[str] = set()
        self.down: set[str] = set()
        self.seen_paths: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        inst = request.url.host.split(".")[0]
        path = request.url.path
        self.seen_paths.append(path)
        if inst in self.down:
            raise httpx.ConnectError("down")
        if path == "/v1/auth/request-code":
            return httpx.Response(202, json={"message": "If registered, a mock code was generated."})
        if path == "/v1/auth/verify-code":
            body = json.loads(request.content)
            if body["code"] != CODE:
                return httpx.Response(401, json={"detail": "Invalid or expired verification code"})
            return httpx.Response(200, json={"access_token": f"tok-{inst}", "token_type": "bearer", "expires_in": 1800})
        if path.endswith("-offers"):
            return httpx.Response(200, json=[{"loan_type": "personal_loan"}])
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if token != f"tok-{inst}" or token in self.revoked:
            return httpx.Response(401, json={"detail": "Invalid or expired access token"})
        if path == "/v1/customers/me":
            return httpx.Response(200, json={"id": f"{inst}-customer-001", "email": f"customer1@{inst}.example.test"})
        if path == "/v1/accounts":
            return httpx.Response(200, json=ACCOUNTS.get(inst, []))
        if path.startswith("/v1/accounts/") and path.endswith("/transactions"):
            offset, limit = int(request.url.params["offset"]), int(request.url.params["limit"])
            return httpx.Response(200, json={"items": TX[offset:offset + limit], "total": len(TX), "limit": limit, "offset": offset})
        if path.startswith("/v1/accounts/"):
            match = [a for a in ACCOUNTS.get(inst, []) if a["id"] == path.rsplit("/", 1)[1]]
            return httpx.Response(200, json=match[0]) if match else httpx.Response(404, json={"detail": "Account not found"})
        if path == "/v1/loan-applications" and request.method == "GET":
            return httpx.Response(200, json=[{"id": "a1", "status": "declined"}])
        if path == "/v1/loan-applications/a1":
            return httpx.Response(200, json={"id": "a1", "status": "declined"})
        if path.startswith("/v1/loan-applications/"):
            return httpx.Response(404, json={"detail": "Loan application not found"})
        return httpx.Response(404, json={"detail": "Not Found"})


@pytest.fixture
def services():
    return FakeServices()


@pytest.fixture
def api(services):
    hosts = {f"{name}_url": f"http://{name}.test" for name in ("chase", "amex", "pnc", "discover", "loans", "mortgages")}
    with TestClient(create_app(Settings(_env_file=None, **hosts), httpx.MockTransport(services))) as client:
        client.headers["X-Session-Id"] = client.post("/api/v1/sessions").json()["session_id"]
        yield client


def connect(api, inst):
    email = f"customer1@{inst}.example.test"
    assert api.post(f"/api/v1/institutions/{inst}/request-code", json={"email": email}).status_code == 202
    return api.post(f"/api/v1/institutions/{inst}/verify-code", json={"email": email, "code": CODE})


def test_requires_a_session(api):
    assert api.get("/api/v1/accounts", headers={"X-Session-Id": "nope"}).status_code == 401


def test_connect_keeps_token_server_side(api):
    response = connect(api, "chase")
    assert response.status_code == 200
    assert "tok-chase" not in response.text
    listing = api.get("/api/v1/institutions").json()
    assert [i["id"] for i in listing if i["connected"]] == ["chase"]


def test_wrong_code_is_401_and_does_not_connect(api):
    response = api.post("/api/v1/institutions/chase/verify-code", json={"email": "a@b.co", "code": "000000"})
    assert response.status_code == 401
    assert response.json()["detail"]["institution_id"] == "chase"
    assert not any(i["connected"] for i in api.get("/api/v1/institutions").json())


def test_accounts_fan_out_only_to_connected_banks(api, services):
    connect(api, "chase")
    connect(api, "amex")
    body = api.get("/api/v1/accounts").json()
    assert {a["institution_id"] for a in body["items"]} == {"chase", "amex"}
    assert body["errors"] == []


def test_partial_failure_is_reported_not_hidden(api, services):
    connect(api, "chase")
    connect(api, "amex")
    services.down.add("amex")
    body = api.get("/api/v1/accounts").json()
    assert [a["institution_id"] for a in body["items"]] == ["chase"]
    assert body["errors"][0]["institution_id"] == "amex" and body["errors"][0]["status"] == 502


def test_account_lookup_finds_owner_and_404s_otherwise(api):
    connect(api, "chase")
    connect(api, "amex")
    assert api.get("/api/v1/accounts/amex-customer-001-credit_card").json()["institution_id"] == "amex"
    assert api.get("/api/v1/accounts/someone-elses").status_code == 404


def test_unsafe_ids_are_rejected_before_any_upstream_call(api, services):
    connect(api, "chase")
    services.seen_paths.clear()
    assert api.get("/api/v1/accounts/..%2F..%2Fauth").status_code in (404, 422)
    assert all("auth" not in path for path in services.seen_paths)


def test_all_transactions_follow_pagination(api):
    connect(api, "chase")
    body = api.get("/api/v1/transactions").json()
    assert len(body["items"]) == 150


def test_upstream_401_drops_the_connection(api, services):
    connect(api, "chase")
    services.revoked.add("tok-chase")
    assert api.get("/api/v1/accounts").json()["errors"][0]["status"] == 401
    assert not any(i["connected"] for i in api.get("/api/v1/institutions").json())


def test_lender_gating_and_declined_schedule(api):
    assert api.get("/api/v1/lenders/loans/applications").json() == {"connected": False, "items": []}
    assert api.get("/api/v1/lenders/loans/offers").status_code == 200
    connect(api, "loans")
    assert api.get("/api/v1/lenders/loans/applications/a1/schedule").json()["kind"] == "declined"
    assert api.get("/api/v1/lenders/loans/applications/zzz/schedule").json()["kind"] == "not_found"
    assert api.get("/api/v1/lenders/chase/offers").status_code == 404


def test_transaction_date_order_is_validated(api):
    connect(api, "chase")
    response = api.get("/api/v1/accounts/chase-customer-001-checking/transactions?start_date=2026-10-02&end_date=2026-10-01")
    assert response.status_code == 422
