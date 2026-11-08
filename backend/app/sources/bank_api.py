"""Client for the partner-bank API (every mock bank instance speaks the same API).

This is the "Zelle-style partnership" from our pitch: banks expose one standard API,
and Capital Insight connects with the customer's consent (email + last 4 of SSN,
then a 6-digit code). One client class works for every bank; only base_url changes.

Raw bank JSON never leaves this file: it is mapped to domain models right here.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import httpx

from app.domain.errors import DomainError, InvalidRequestError
from app.domain.models import Account, AccountType, Transaction


class BankUnavailableError(RuntimeError):
    """The bank is down or answered with something unusable (maps to HTTP 502)."""


class BankAuthError(DomainError):
    """The access token expired or was revoked: the user must reconnect this bank."""


@dataclass(frozen=True)
class BankToken:
    access_token: str
    expires_in_seconds: int


def to_account(raw: dict[str, Any], institution: str) -> Account | None:
    try:
        acct_type = AccountType(raw["type"])
    except ValueError:
        return None  # a product we don't model yet: skip it, don't crash
    limit = raw.get("credit_limit")
    return Account(
        id=str(raw["id"]),
        institution=institution,
        type=acct_type,
        nickname=str(raw.get("nickname") or acct_type.value),
        balance=Decimal(str(raw["balance"])),
        annual_rate=Decimal(str(raw.get("annual_rate", "0"))),
        credit_limit=Decimal(str(limit)) if limit is not None else None,
    )


def to_transaction(raw: dict[str, Any]) -> Transaction:
    return Transaction(
        id=str(raw["id"]),
        account_id=str(raw["account_id"]),
        posted_on=date.fromisoformat(raw["posted_on"]),
        amount=Decimal(str(raw["amount"])),
        description=str(raw["description"]),
        category=str(raw["category"]),
    )


class BankApiClient:
    def __init__(self, http: httpx.AsyncClient, institution: str) -> None:
        self._http = http  # injected: base_url set per bank, shared pool, mockable in tests
        self.institution = institution

    async def _request(
        self, method: str, path: str, *, token: str | None = None, **kwargs: Any
    ) -> Any:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        try:
            resp = await self._http.request(method, path, headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise BankUnavailableError(f"{self.institution} is unreachable") from exc
        if resp.status_code == 401:
            raise BankAuthError(f"Your {self.institution} connection expired. Reconnect it.")
        if resp.status_code in (400, 422, 429):
            # User-fixable (wrong code, too many attempts): pass the bank's message along.
            raise InvalidRequestError(resp.json().get("detail", "Request rejected by the bank"))
        if resp.is_error:
            raise BankUnavailableError(f"{self.institution} returned HTTP {resp.status_code}")
        return resp.json()

    # --- linking (consent) ---------------------------------------------------------

    async def start_consent(self, email: str, ssn_last4: str) -> str:
        body = await self._request(
            "POST", "/v1/consents", json={"email": email, "ssn_last4": ssn_last4}
        )
        return body["consent_id"]

    async def exchange_code(self, consent_id: str, code: str) -> BankToken:
        body = await self._request(
            "POST", f"/v1/consents/{quote(consent_id, safe='')}/token", json={"code": code}
        )
        return BankToken(body["access_token"], int(body["expires_in_seconds"]))

    # --- data -------------------------------------------------------------------------

    async def accounts(self, token: str) -> tuple[Account, ...]:
        body = await self._request("GET", "/v1/accounts", token=token)
        mapped = (to_account(raw, self.institution) for raw in body["accounts"])
        return tuple(a for a in mapped if a is not None)

    async def transactions(
        self, token: str, account_id: str, start: date | None = None, end: date | None = None
    ) -> list[Transaction]:
        params = {k: v.isoformat() for k, v in (("start_date", start), ("end_date", end)) if v}
        body = await self._request(
            "GET",
            f"/v1/accounts/{quote(account_id, safe='')}/transactions",
            token=token,
            params=params,
        )
        return [to_transaction(raw) for raw in body["transactions"]]
