"""Server-side Plaid REST adapter and atomic incremental transaction import."""

import asyncio
import json
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from cryptography.fernet import InvalidToken
from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from .models import CachedTransaction, Connection, PlaidState


class PlaidAPIError(HTTPException):
    """Expose only stable error identifiers, never Plaid's raw error body."""

    def __init__(self, error_code: str, request_id: str | None = None):
        self.error_code = error_code
        detail = {"provider": "plaid", "error_code": error_code}
        if request_id:
            detail["request_id"] = request_id
        status_code = 502
        if error_code in {"ITEM_LOGIN_REQUIRED", "INVALID_ACCESS_TOKEN", "ITEM_NOT_FOUND"}:
            status_code = 409
            detail["action"] = "Reconnect this institution using Plaid Link."
        super().__init__(status_code=status_code, detail=detail)


class PlaidClient:
    def __init__(self, settings: Any, http_client: httpx.AsyncClient):
        self.settings = settings
        self.http_client = http_client

    async def call(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self.settings
        if not settings.plaid_client_id or not settings.plaid_secret:
            raise HTTPException(503, detail="Plaid is not configured. Set PLAID_CLIENT_ID and PLAID_SECRET on the backend.")
        hosts = {"sandbox": "https://sandbox.plaid.com", "production": "https://production.plaid.com"}
        if settings.plaid_environment not in hosts:
            raise HTTPException(503, detail="Unsupported Plaid environment.")
        secret = settings.plaid_secret.get_secret_value()
        try:
            response = await self.http_client.post(
                hosts[settings.plaid_environment] + path,
                json={**payload, "client_id": settings.plaid_client_id.get_secret_value(), "secret": secret},
                headers={"Plaid-Version": "2020-09-14"},
                timeout=settings.request_timeout_seconds,
            )
        except httpx.RequestError:
            raise PlaidAPIError("UPSTREAM_UNAVAILABLE") from None
        try:
            # Decimal parsing preserves the exact JSON amount, before normalization.
            data = json.loads(response.content, parse_float=Decimal)
        except (ValueError, UnicodeDecodeError):
            raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE") from None
        if not isinstance(data, dict):
            raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE")
        if not response.is_success:
            error_code = data.get("error_code")
            request_id = data.get("request_id")
            # Provider messages can contain identifying data. Never forward them.
            raise PlaidAPIError(
                error_code if isinstance(error_code, str) else "UPSTREAM_ERROR",
                request_id if isinstance(request_id, str) else None,
            )
        return data


def client_for(request: Request) -> PlaidClient:
    return PlaidClient(request.app.state.settings, request.app.state.http_client)


def require_plaid(connection: Connection) -> None:
    if connection.kind != "plaid" or connection.provider != "plaid":
        raise HTTPException(404, detail="Plaid connection not found.")


def access_token_for(request: Request, connection: Connection) -> str:
    require_plaid(connection)
    try:
        return request.app.state.cipher.decrypt(connection.encrypted_token.encode()).decode()
    except (InvalidToken, ValueError, UnicodeDecodeError):
        raise HTTPException(409, detail="Connection credentials are unavailable. Reconnect this institution.") from None


def decimal_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            raise InvalidOperation
        return format(result, "f")
    except (InvalidOperation, ValueError):
        raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE") from None


def normalize_account(connection_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    source_id = raw["account_id"]
    source_type = raw.get("type", "unknown")
    subtype = raw.get("subtype")
    balances = raw.get("balances") or {}
    kind = "liability" if source_type in {"credit", "loan"} else (
        "asset" if source_type in {"depository", "investment"} else "unknown"
    )
    account_type = (subtype or source_type).replace(" ", "_")
    return {
        "id": f"{connection_id}:{source_id}",
        "connection_id": connection_id,
        "provider": "plaid",
        "source_account_id": source_id,
        "source_account_type": source_type,
        "account_type": account_type,
        "account_name": raw.get("name") or raw.get("official_name") or "Plaid account",
        "account_number_last4": raw.get("mask"),
        "currency": balances.get("iso_currency_code") or balances.get("unofficial_currency_code"),
        "balance": decimal_string(balances.get("current")),
        "balance_kind": kind,
        "balance_as_of": balances.get("last_updated_datetime"),
        "balance_is_cached": True,
    }


async def get_accounts(request: Request, connection: Connection) -> list[dict[str, Any]]:
    token = access_token_for(request, connection)
    result = await client_for(request).call("/accounts/get", {"access_token": token})
    try:
        return [normalize_account(connection.id, raw) for raw in result["accounts"]]
    except (KeyError, TypeError, AttributeError):
        raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE") from None


def normalize_transaction(connection_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    try:
        amount = Decimal(decimal_string(raw["amount"]))
        account_id = raw["account_id"]
        transaction_id = raw["transaction_id"]
        category = (raw.get("personal_finance_category") or {}).get("primary")
        return {
            "id": f"{connection_id}:{transaction_id}",
            "connection_id": connection_id,
            "provider": "plaid",
            "source_transaction_id": transaction_id,
            "account_id": f"{connection_id}:{account_id}",
            "source_account_id": account_id,
            "transaction_date": raw["date"],
            "description": raw.get("name") or "Transaction",
            "merchant": raw.get("merchant_name"),
            "category": category.lower() if category else "other",
            "amount": format(abs(amount), "f"),
            "direction": "debit" if amount >= 0 else "credit",
            "currency": raw.get("iso_currency_code") or raw.get("unofficial_currency_code"),
            "pending": bool(raw.get("pending", False)),
        }
    except (KeyError, TypeError, AttributeError):
        raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE") from None


async def _collect_updates(client: PlaidClient, token: str, original_cursor: str | None):
    # Retry only pagination mutations, always from the original committed cursor.
    for attempt in range(3):
        cursor = original_cursor
        pages = []
        seen_cursors = {cursor}
        try:
            while True:
                payload = {"access_token": token, "count": 500}
                if cursor is not None:
                    payload["cursor"] = cursor
                page = await client.call("/transactions/sync", payload)
                if not all(isinstance(page.get(key), list) for key in ("added", "modified", "removed")):
                    raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE")
                next_cursor = page.get("next_cursor")
                has_more = page.get("has_more")
                if not isinstance(next_cursor, str) or not isinstance(has_more, bool):
                    raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE")
                pages.append(page)
                if not has_more:
                    return pages, next_cursor
                if next_cursor in seen_cursors:
                    raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE")
                seen_cursors.add(next_cursor)
                cursor = next_cursor
        except PlaidAPIError as error:
            if error.error_code != "TRANSACTIONS_SYNC_MUTATION_DURING_PAGINATION" or attempt == 2:
                raise
    raise PlaidAPIError("UPSTREAM_ERROR")


async def sync_transactions(request: Request, session: Session, connection: Connection) -> dict[str, int]:
    token = access_token_for(request, connection)
    connection_id = connection.id
    # Serialize this process's imports; the cursor compare-and-swap also protects
    # multiple backend workers sharing PostgreSQL.
    if not hasattr(request.app.state, "plaid_sync_locks"):
        request.app.state.plaid_sync_locks = {}
    lock = request.app.state.plaid_sync_locks.setdefault(connection_id, asyncio.Lock())
    async with lock:
        state = session.get(PlaidState, connection_id)
        if state is None:
            state = PlaidState(connection_id=connection_id, cursor=None)
            session.add(state)
            try:
                session.commit()
            except Exception:
                session.rollback()
                state = session.get(PlaidState, connection_id)
                if state is None:
                    raise
        original_cursor = state.cursor
        # Release the read transaction before waiting for Plaid's network calls.
        session.rollback()
        pages, next_cursor = await _collect_updates(client_for(request), token, original_cursor)

        # Normalize everything before touching cached rows. A malformed later page
        # must not leave earlier pages imported or advance the committed cursor.
        operations = {}
        counts = {"added": 0, "modified": 0, "removed": 0}
        try:
            for page in pages:
                for kind in ("added", "modified"):
                    for raw in page[kind]:
                        operations[raw["transaction_id"]] = normalize_transaction(connection_id, raw)
                        counts[kind] += 1
                for raw in page["removed"]:
                    operations[raw["transaction_id"]] = None
                    counts["removed"] += 1
        except (KeyError, TypeError):
            raise PlaidAPIError("INVALID_UPSTREAM_RESPONSE") from None

        try:
            guard = PlaidState.cursor.is_(None) if original_cursor is None else PlaidState.cursor == original_cursor
            result = session.execute(
                update(PlaidState)
                .where(PlaidState.connection_id == connection_id, guard)
                .values(cursor=next_cursor)
                .execution_options(synchronize_session=False)
            )
            if result.rowcount != 1:
                raise HTTPException(409, detail="Another sync completed for this connection. Retry the sync.")
            records = {
                row.remote_id: row
                for row in session.scalars(select(CachedTransaction).where(CachedTransaction.connection_id == connection_id))
            }
            for remote_id, payload in operations.items():
                existing = records.get(remote_id)
                if payload is None:
                    if existing is not None:
                        session.delete(existing)
                        records.pop(remote_id)
                elif existing is not None:
                    existing.payload = payload
                else:
                    record = CachedTransaction(connection_id=connection_id, remote_id=remote_id, payload=payload)
                    session.add(record)
                    records[remote_id] = record
            session.commit()
        except Exception:
            session.rollback()
            raise
        return counts
