"""Capital One Nessie adapter: read-only (GET), which is all an insights app needs.

Endpoints used (all GET, key as the `key` query parameter):
    /customers                          discovery (scripts/nessie_check.py)
    /customers/{id}                     name
    /customers/{id}/accounts            Checking, Savings, Credit Card
    /accounts/{id}/loans                home -> mortgage, auto / small business -> loan
    /accounts/{id}/purchases            spending (merchant category via /merchants/{id})
    /accounts/{id}/deposits             income
    /accounts/{id}/withdrawals          cash out
    /accounts/{id}/bills                upcoming obligations

Gaps in Nessie data, handled explicitly instead of guessed:
- No credit limit or interest rate on accounts -> None / 0. Utilization shows "unknown"
  until the user enters their limit (or another source provides it).
- credit_score on loans is a static sandbox value, not a bureau score.

Raw Nessie JSON never leaves this file. Records we can't parse are skipped, never guessed.
"""

import asyncio
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from app.domain.errors import NotFoundError
from app.domain.models import Account, AccountType, FinancialProfile, Transaction
from app.engine import cashflow

INSTITUTION = "Capital One"

_ACCOUNT_TYPES = {
    "checking": AccountType.CHECKING,
    "savings": AccountType.SAVINGS,
    "credit card": AccountType.CREDIT_CARD,
}


class NessieError(RuntimeError):
    """Nessie is down or returned something we can't use (maps to HTTP 502)."""


class Bill(BaseModel):
    id: str
    account_id: str
    payee: str
    amount: Decimal
    next_due: date | None
    recurring_day: int | None
    status: str


# --- parsing helpers: tolerate missing or odd fields, never crash -----------------------


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _money(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _is_cancelled(raw: dict[str, Any]) -> bool:
    return str(raw.get("status", "")).lower() == "cancelled"


# --- mapping (pure functions, unit-tested) ------------------------------------------------


def to_account(raw: dict[str, Any]) -> Account | None:
    acct_type = _ACCOUNT_TYPES.get(str(raw.get("type", "")).strip().lower())
    balance = _money(raw.get("balance", 0))
    if acct_type is None or balance is None:
        return None
    return Account(
        id=str(raw["_id"]),
        institution=INSTITUTION,
        type=acct_type,
        nickname=str(raw.get("nickname") or acct_type.value.replace("_", " ").title()),
        # Debt is stored as a positive "amount owed"; Nessie may use either sign.
        balance=abs(balance) if acct_type.is_debt else max(balance, Decimal("0")),
    )


def loan_to_account(raw: dict[str, Any]) -> Account | None:
    if str(raw.get("status", "")).lower() != "approved":
        return None  # pending/declined loans aren't debt yet
    amount = _money(raw.get("amount"))
    if amount is None:
        return None
    kind = str(raw.get("type", "")).lower()
    return Account(
        id=str(raw["_id"]),
        institution=INSTITUTION,
        type=AccountType.MORTGAGE if kind == "home" else AccountType.LOAN,
        nickname=str(raw.get("description") or f"{kind.title()} loan"),
        balance=abs(amount),
    )


def to_transaction(
    raw: dict[str, Any], account_id: str, kind: str, merchant_categories: dict[str, str]
) -> Transaction | None:
    """kind: 'purchase' | 'deposit' | 'withdrawal'. Returns None for unusable records."""
    if _is_cancelled(raw):
        return None
    posted = _date(raw.get("purchase_date") if kind == "purchase" else raw.get("transaction_date"))
    amount = _money(raw.get("amount"))
    if posted is None or amount is None:
        return None

    if kind == "deposit":
        signed, category = abs(amount), "income"
    elif kind == "withdrawal":
        signed, category = -abs(amount), "cash"
    else:
        signed = -abs(amount)
        category = merchant_categories.get(str(raw.get("merchant_id")), "shopping")
    return Transaction(
        id=str(raw["_id"]),
        account_id=account_id,
        posted_on=posted,
        amount=signed,
        description=str(raw.get("description") or kind.title()),
        category=category,
    )


def to_bill(raw: dict[str, Any], account_id: str) -> Bill | None:
    amount = _money(raw.get("payment_amount"))
    if _is_cancelled(raw) or amount is None:
        return None
    day = raw.get("recurring_date")
    return Bill(
        id=str(raw["_id"]),
        account_id=account_id,
        payee=str(raw.get("payee") or raw.get("nickname") or "Bill"),
        amount=abs(amount),
        next_due=_date(raw.get("upcoming_payment_date") or raw.get("payment_date")),
        recurring_day=int(day) if isinstance(day, int) and 1 <= day <= 31 else None,
        status=str(raw.get("status", "")),
    )


def merchant_category(raw: dict[str, Any]) -> str:
    cats = raw.get("category")
    first = cats[0] if isinstance(cats, list) and cats else cats
    return str(first).strip().lower() if first else "shopping"


# --- client -------------------------------------------------------------------------------


class NessieSource:
    def __init__(self, client: httpx.AsyncClient, api_key: str) -> None:
        # Injected client: tests pass a mock transport; the app shares one pool.
        self._client = client
        self._api_key = api_key

    async def _get(self, path: str) -> Any:
        try:
            resp = await self._client.get(path, params={"key": self._api_key})
        except httpx.HTTPError as exc:
            raise NessieError(f"Nessie request failed: {exc.__class__.__name__}") from exc
        if resp.status_code == 404:
            raise NotFoundError(f"Nessie resource not found: {path}")
        if resp.is_error:
            # Never echo the URL: it contains the API key as a query parameter.
            raise NessieError(f"Nessie returned HTTP {resp.status_code} for {path}")
        return resp.json()

    async def _get_list(self, path: str) -> list[dict[str, Any]]:
        """GET a collection. Missing sub-collections (404) count as empty."""
        try:
            body = await self._get(path)
        except NotFoundError:
            return []
        return body if isinstance(body, list) else []

    async def list_customers(self) -> list[dict[str, str]]:
        return [
            {"id": str(c["_id"]), "name": f"{c.get('first_name', '')} {c.get('last_name', '')}"}
            for c in await self._get_list("/customers")
        ]

    async def _raw_accounts(self, customer_id: str) -> list[dict[str, Any]]:
        return await self._get_list(f"/customers/{quote(customer_id, safe='')}/accounts")

    async def _transactions_for(self, account_ids: list[str]) -> list[Transaction]:
        # 1) Every account's purchases, deposits and withdrawals, fetched concurrently.
        jobs = [
            (acct, kind) for acct in account_ids for kind in ("purchase", "deposit", "withdrawal")
        ]
        results = await asyncio.gather(
            *(self._get_list(f"/accounts/{quote(acct, safe='')}/{kind}s") for acct, kind in jobs)
        )
        fetched = list(zip(jobs, results, strict=True))

        # 2) Each merchant looked up once, for spending categories.
        merchant_ids = sorted(
            {
                str(raw["merchant_id"])
                for (_, kind), rows in fetched
                if kind == "purchase"
                for raw in rows
                if raw.get("merchant_id")
            }
        )
        merchants = await asyncio.gather(
            *(self._get(f"/merchants/{quote(m, safe='')}") for m in merchant_ids),
            return_exceptions=True,  # a missing merchant just means "shopping"
        )
        categories = {
            m: merchant_category(raw)
            for m, raw in zip(merchant_ids, merchants, strict=True)
            if isinstance(raw, dict)
        }

        # 3) Map to domain transactions, newest first.
        txns = [
            txn
            for (acct, kind), rows in fetched
            for raw in rows
            if (txn := to_transaction(raw, acct, kind, categories)) is not None
        ]
        return sorted(txns, key=lambda t: (t.posted_on, t.id), reverse=True)

    async def get_transactions(self, customer_id: str) -> list[Transaction]:
        await self._get(f"/customers/{quote(customer_id, safe='')}")  # 404 if unknown
        raw_accounts = await self._raw_accounts(customer_id)
        return await self._transactions_for([str(a["_id"]) for a in raw_accounts])

    async def get_bills(self, customer_id: str) -> list[Bill]:
        raw_accounts = await self._raw_accounts(customer_id)
        ids = [str(a["_id"]) for a in raw_accounts]
        results = await asyncio.gather(
            *(self._get_list(f"/accounts/{quote(i, safe='')}/bills") for i in ids)
        )
        return [
            b
            for account_id, rows in zip(ids, results, strict=True)
            for raw in rows
            if (b := to_bill(raw, account_id)) is not None
        ]

    async def get_profile(self, customer_id: str) -> FinancialProfile:
        cid = quote(customer_id, safe="")  # an ID must never be able to change the path
        customer, raw_accounts = await asyncio.gather(
            self._get(f"/customers/{cid}"), self._raw_accounts(customer_id)
        )
        ids = [str(a["_id"]) for a in raw_accounts]
        loans_per_account = await asyncio.gather(
            *(self._get_list(f"/accounts/{quote(i, safe='')}/loans") for i in ids)
        )
        loans = [loan for rows in loans_per_account for loan in rows]

        accounts = [a for a in map(to_account, raw_accounts) if a is not None]
        accounts += [a for a in map(loan_to_account, loans) if a is not None]
        scores = [
            s
            for loan in loans
            if isinstance(s := loan.get("credit_score"), int) and 300 <= s <= 850
        ]

        flow = cashflow.summarize(await self._transactions_for(ids))
        name = f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        return FinancialProfile(
            customer_id=customer_id,
            display_name=name or customer_id,
            accounts=tuple(accounts),
            monthly_income=flow.monthly_income or None,
            monthly_expenses=flow.monthly_spending or None,
            credit_score=scores[0] if scores else None,
        )
