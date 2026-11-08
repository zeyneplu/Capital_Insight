import asyncio
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import select
from ..dependencies import SessionDep, UserDep
from ..models import Connection
from ..providers import bank_accounts, projections, mock_call, mock_token, scoped_id, segment
from ..schemas import AccountCollection, ProjectionCollection, TransactionPage, DashboardOut

router = APIRouter(prefix="/v1", tags=["Portfolio"])


def user_connections(session, user, kinds: set[str], connection_id: str | None = None):
    query = select(Connection).where(Connection.user_id == user.id, Connection.kind.in_(kinds))
    if connection_id:
        query = query.where(Connection.id == connection_id)
    return session.scalars(query.order_by(Connection.created_at, Connection.id)).all()


async def collect(request: Request, connections, resource: str):
    async def fetch(connection):
        try:
            if resource == "accounts":
                if connection.kind == "plaid":
                    from ..plaid import get_accounts
                    items = await get_accounts(request, connection)
                else:
                    items = await bank_accounts(request, connection)
            else:
                items = await projections(request, connection, resource)
            return items, None
        except HTTPException as error:
            return [], {"connection_id": connection.id, "provider": connection.provider,
                        "status_code": error.status_code, "message": "Provider unavailable or requires reconnection"}
        except (KeyError, TypeError, ValueError):
            return [], {"connection_id": connection.id, "provider": connection.provider,
                        "status_code": 502, "message": "Invalid provider response"}
    responses = await asyncio.gather(*(fetch(connection) for connection in connections))
    return {"items": [item for items, _ in responses for item in items],
            "errors": [error for _, error in responses if error],
            "complete": all(error is None for _, error in responses)}


@router.get("/accounts", response_model=AccountCollection, summary="Aggregate your linked bank and Plaid account snapshots")
async def accounts(request: Request, session: SessionDep, user: UserDep,
                   connection_id: str | None = None, account_type: str | None = None):
    result = await collect(request, user_connections(session, user, {"mock_bank", "plaid"}, connection_id), "accounts")
    if account_type:
        result["items"] = [item for item in result["items"] if item["account_type"] == account_type]
    return result


@router.get("/loans", response_model=ProjectionCollection, summary="Aggregate approved personal and auto loan projections")
async def loans(request: Request, session: SessionDep, user: UserDep):
    return await collect(request, user_connections(session, user, {"mock_loan"}), "loans")


@router.get("/mortgages", response_model=ProjectionCollection, summary="Aggregate approved mortgage projections from linked lenders")
async def mortgages(request: Request, session: SessionDep, user: UserDep):
    return await collect(request, user_connections(session, user, {"mock_loan", "mock_mortgage"}), "mortgages")


@router.get("/accounts/{account_id}/transactions", response_model=TransactionPage,
             summary="Read a connected mock bank account's transactions",
             description="account_id is the composite id from /v1/accounts. For Plaid use its cached transaction route after syncing.")
async def transactions(account_id: str, request: Request, session: SessionDep, user: UserDep,
                       limit: Annotated[int, Query(ge=1, le=100)] = 50,
                       offset: Annotated[int, Query(ge=0)] = 0,
                       start_date: date | None = None, end_date: date | None = None,
                       category: str | None = None):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date")
    if ":" not in account_id:
        raise HTTPException(404, "Account not found")
    connection_id, remote_id = account_id.split(":", 1)
    connection = session.scalar(select(Connection).where(Connection.id == connection_id, Connection.user_id == user.id))
    if connection is None:
        raise HTTPException(404, "Account not found")
    if connection.kind == "plaid":
        raise HTTPException(409, "Use /v1/plaid/connections/{connection_id}/transactions after sync")
    if connection.kind != "mock_bank":
        raise HTTPException(404, "Bank account not found")
    params = {"limit": limit, "offset": offset}
    for name, value in (("start_date", start_date), ("end_date", end_date), ("category", category)):
        if value is not None:
            params[name] = str(value)
    page = await mock_call(request, connection.provider, f"/v1/accounts/{segment(remote_id)}/transactions",
                           token=mock_token(request, connection), params=params)
    page["items"] = [{**item, "source_transaction_id": item["id"],
        "id": scoped_id(connection.id, item["id"]), "account_id": account_id} for item in page["items"]]
    return page


@router.get("/dashboard", response_model=DashboardOut,
             summary="Summarize known account snapshots without treating loan projections as live balances")
async def dashboard(request: Request, session: SessionDep, user: UserDep):
    connections = user_connections(session, user, {"mock_bank", "plaid"})
    result = await collect(request, connections, "accounts")
    grouped = defaultdict(lambda: {"assets": Decimal("0.00"), "liabilities": Decimal("0.00")})
    excluded = 0
    for account in result["items"]:
        if account.get("balance") is None or not account.get("currency") or account["balance_kind"] == "unknown":
            excluded += 1
            continue
        key = "assets" if account["balance_kind"] == "asset" else "liabilities"
        grouped[account["currency"]][key] += Decimal(str(account["balance"]))
    return {"by_currency": [{"currency": currency, **values, "net_balance": values["assets"]-values["liabilities"]}
                             for currency, values in sorted(grouped.items())],
            "account_count": len(result["items"]), "connection_count": len(connections),
            "excluded_accounts": excluded, "errors": result["errors"], "complete": result["complete"],
            "coverage": "Linked bank/Plaid account snapshots only. Unknown balances and loan/mortgage application projections are excluded. Duplicate real accounts across providers require user reconciliation; this is not complete net worth."}
