"""Tests the core's bank client against payloads shaped exactly like mock-bank's API."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.domain.errors import InvalidRequestError
from app.domain.models import AccountType
from app.sources.bank_api import BankApiClient, BankAuthError, BankUnavailableError

ACCOUNTS = {
    "accounts": [
        {"id": "a1", "type": "credit_card", "nickname": "Comet Rewards", "mask": "1234",
         "currency": "USD", "balance": "600.00", "annual_rate": "0.1800",
         "credit_limit": "2500.00"},
        {"id": "a2", "type": "mortgage", "nickname": "Home", "mask": "9", "currency": "USD",
         "balance": "284000.00", "annual_rate": "0.0625", "credit_limit": None},
        {"id": "a3", "type": "brokerage", "nickname": "?", "mask": "0", "currency": "USD",
         "balance": "1.00", "annual_rate": "0", "credit_limit": None},
    ]
}  # fmt: skip


def client_for(handler) -> BankApiClient:
    http = httpx.AsyncClient(base_url="http://bank.test", transport=httpx.MockTransport(handler))
    return BankApiClient(http, institution="Comet Card (demo)")


async def test_consent_flow_and_accounts():
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/consents":
            return httpx.Response(202, json={"consent_id": "c-1", "expires_in_seconds": 600})
        if req.url.path == "/v1/consents/c-1/token":
            return httpx.Response(200, json={"access_token": "tok", "expires_in_seconds": 60})
        if req.url.path == "/v1/accounts":
            assert req.headers["Authorization"] == "Bearer tok"
            return httpx.Response(200, json=ACCOUNTS)
        return httpx.Response(404)

    bank = client_for(handler)
    consent_id = await bank.start_consent("alex.rivera@example.com", "4821")
    token = await bank.exchange_code(consent_id, "123456")
    accounts = await bank.accounts(token.access_token)

    assert [a.type for a in accounts] == [AccountType.CREDIT_CARD, AccountType.MORTGAGE]
    assert accounts[0].credit_limit == Decimal("2500.00")
    assert accounts[0].institution == "Comet Card (demo)"
    assert accounts[1].type.is_debt


async def test_transactions_are_mapped_and_filtered():
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params["start_date"] == "2026-10-01"
        return httpx.Response(
            200,
            json={"transactions": [{"id": "t1", "account_id": "a1", "posted_on": "2026-10-03",
                                    "amount": "-42.10", "description": "Corner Grocery",
                                    "category": "groceries"}]},
        )  # fmt: skip

    txns = await client_for(handler).transactions("tok", "a1", start=date(2026, 10, 1))
    assert txns[0].amount == Decimal("-42.10")
    assert txns[0].posted_on == date(2026, 10, 3)


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, BankAuthError), (400, InvalidRequestError), (429, InvalidRequestError),
     (500, BankUnavailableError)],
)  # fmt: skip
async def test_errors_are_translated(status, error):
    bank = client_for(lambda req: httpx.Response(status, json={"detail": "nope"}))
    with pytest.raises(error):
        await bank.accounts("tok")


async def test_network_failure_is_bank_unavailable():
    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(BankUnavailableError):
        await client_for(handler).accounts("tok")
