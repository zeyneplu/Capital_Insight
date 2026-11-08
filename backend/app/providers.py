"""Read-only adapters for fixed, configured mock institution endpoints."""
from decimal import Decimal
import json
from urllib.parse import quote
import httpx
from cryptography.fernet import InvalidToken
from fastapi import HTTPException, Request
from .database import utcnow

PROVIDERS = {
    "chase": ("Chase Mock Bank", "mock_bank"),
    "amex": ("American Express Mock Bank", "mock_bank"),
    "pnc": ("PNC Mock Bank", "mock_bank"),
    "discover": ("Discover Mock Bank", "mock_bank"),
    "loans": ("Mock Loans", "mock_loan"),
    "mortgages": ("Mock Mortgages", "mock_mortgage"),
}
ASSETS = {"checking", "savings", "cd", "ira"}
LIABILITIES = {"credit_card", "personal_loan", "auto_loan", "mortgage"}


def scoped_id(connection_id: str, remote_id: str) -> str:
    return f"{connection_id}:{remote_id}"


def segment(value: str) -> str:
    return quote(value, safe="")


def mock_token(request: Request, connection) -> str:
    if connection.expires_at and connection.expires_at <= utcnow():
        raise HTTPException(409, "Connection expired; repeat mock authorization")
    try:
        return request.app.state.cipher.decrypt(connection.encrypted_token.encode()).decode()
    except InvalidToken:
        raise HTTPException(409, "Connection credentials unavailable; reconnect")


async def mock_call(request: Request, provider: str, path: str, *, method="GET", token=None, body=None, params=None):
    settings = request.app.state.settings
    if provider not in PROVIDERS or provider not in settings.mock_service_urls:
        raise HTTPException(404, "Provider not configured")
    url = settings.mock_service_urls[provider].rstrip("/") + path
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = await request.app.state.http_client.request(method, url, headers=headers, json=body, params=params)
    except httpx.RequestError:
        raise HTTPException(502, "Mock service unavailable")
    if response.status_code >= 400:
        if response.status_code == 401 and token:
            raise HTTPException(409, "Connection expired or invalid; reconnect")
        status = response.status_code if response.status_code in {401, 404, 409, 422, 429} else 502
        retry = {"Retry-After": response.headers.get("Retry-After", "30")} if status == 429 else None
        raise HTTPException(status, {"message": "Mock service rejected the request", "provider": provider}, headers=retry)
    try:
        return json.loads(response.text, parse_float=Decimal)
    except (ValueError, TypeError):
        raise HTTPException(502, "Invalid response from mock service")


async def bank_accounts(request: Request, connection):
    raw = await mock_call(request, connection.provider, "/v1/accounts", token=mock_token(request, connection))
    if not isinstance(raw, list):
        raise HTTPException(502, "Invalid account response from mock service")
    result = []
    for account in raw:
        kind = account["account_type"]
        result.append({**account, "source_account_id": account["id"],
            "id": scoped_id(connection.id, account["id"]), "connection_id": connection.id,
            "provider": connection.provider,
            "balance_kind": "asset" if kind in ASSETS else "liability" if kind in LIABILITIES else "unknown"})
    return result


async def projections(request: Request, connection, record_type: str):
    path = "/v1/loans" if connection.kind == "mock_loan" else "/v1/mortgages"
    records = await mock_call(request, connection.provider, path, token=mock_token(request, connection))
    result = []
    for record in records:
        # The generic loan service also has a mortgage product. Keep views disjoint.
        is_mortgage = connection.kind == "mock_mortgage" or record.get("loan_type") == "mortgage"
        if is_mortgage != (record_type == "mortgages"):
            continue
        result.append({**record, "source_record_id": record["id"], "id": scoped_id(connection.id, record["id"]),
            "connection_id": connection.id, "provider": connection.provider,
            "record_kind": "approval_projection", "current_balance": None})
    return result
