"""Accounts and transactions, fanned out across every connected bank."""
import asyncio
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Path, Query

from ..deps import ClientDep, RegistryDep, SessionDep, authed_call
from ..institutions import Institution
from ..upstream import UpstreamError, as_http
from ..schemas import TransactionRequest

router = APIRouter(prefix="/api/v1", tags=["Banking"])

# IDs are interpolated into upstream URLs, so only allow safe characters.
SafeId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,128}$")]
CATEGORY = r"^[a-z_]{1,32}$"


def connected_banks(session, registry: dict[str, Institution]) -> list[Institution]:
    return [i for i in registry.values() if i.service == "mock_bank" and session.active(i.id)]


def failure(error: UpstreamError) -> dict:
    return {"institution_id": error.institution_id, "status": error.status, "detail": error.detail}


@router.get("/accounts", summary="Raw accounts from every connected bank")
async def accounts(session: SessionDep, http: ClientDep, registry: RegistryDep,
                   account_type: Annotated[str | None, Query(pattern=r"^[a-z_]{1,32}$")] = None) -> dict:
    banks = connected_banks(session, registry)
    params = {"account_type": account_type} if account_type else None
    results = await asyncio.gather(
        *(authed_call(http, session, bank, "GET", "/v1/accounts", params=params) for bank in banks),
        return_exceptions=True,
    )
    items: list[Any] = []
    errors: list[dict] = []
    for result in results:
        if isinstance(result, UpstreamError):
            errors.append(failure(result))
        elif isinstance(result, BaseException):
            raise result
        else:
            items.extend(result)
    # Partial results are returned with explicit errors, never silently.
    return {"items": items, "errors": errors}


async def locate(session, http, registry, account_id: str) -> tuple[Institution, dict]:
    """Finds which connected bank owns the account. Each bank answers 404 for others' accounts."""
    banks = connected_banks(session, registry)
    results = await asyncio.gather(
        *(authed_call(http, session, bank, "GET", f"/v1/accounts/{account_id}") for bank in banks),
        return_exceptions=True,
    )
    hard_errors = []
    for bank, result in zip(banks, results):
        if isinstance(result, dict):
            return bank, result
        if isinstance(result, UpstreamError) and result.status != 404:
            hard_errors.append(result)
        elif isinstance(result, BaseException) and not isinstance(result, UpstreamError):
            raise result
    if hard_errors:
        raise as_http(hard_errors[0])
    raise HTTPException(404, "Account not found")


@router.get("/accounts/{account_id}", summary="One account from whichever connected bank owns it")
async def account(account_id: SafeId, session: SessionDep, http: ClientDep, registry: RegistryDep) -> dict:
    _, raw = await locate(session, http, registry, account_id)
    return raw


@router.post("/accounts/{account_id}/transactions", status_code=201, summary="Simulate an owned mock-bank transaction")
async def create_transaction(account_id: SafeId, body: TransactionRequest, session: SessionDep, http: ClientDep, registry: RegistryDep):
    bank, _ = await locate(session,http,registry,account_id)
    try:
        return await authed_call(http,session,bank,"POST",f"/v1/accounts/{account_id}/transactions",json=body.model_dump(mode="json"))
    except UpstreamError as error:
        raise as_http(error) from error


@router.get("/accounts/{account_id}/transactions", summary="A page of transactions (service semantics)")
async def transactions(
    account_id: SafeId, session: SessionDep, http: ClientDep, registry: RegistryDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    start_date: date | None = None,
    end_date: date | None = None,
    category: Annotated[str | None, Query(pattern=CATEGORY)] = None,
) -> dict:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date")
    bank, _ = await locate(session, http, registry, account_id)
    params = {"limit": limit, "offset": offset, "start_date": start_date, "end_date": end_date, "category": category}
    try:
        return await authed_call(http, session, bank, "GET", f"/v1/accounts/{account_id}/transactions",
                                 params={k: str(v) for k, v in params.items() if v is not None})
    except UpstreamError as error:
        raise as_http(error) from error


async def all_transactions(http, session, bank: Institution, account_id: str, params: dict) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while True:
        page = await authed_call(http, session, bank, "GET", f"/v1/accounts/{account_id}/transactions",
                                 params={**params, "limit": "100", "offset": str(offset)})
        items.extend(page["items"])
        offset += len(page["items"])
        if not page["items"] or offset >= page["total"]:
            return items


@router.get("/transactions", summary="Every transaction of every connected account (for dashboards)")
async def every_transaction(session: SessionDep, http: ClientDep, registry: RegistryDep,
                            start_date: date | None = None, end_date: date | None = None) -> dict:
    listing = await accounts(session, http, registry)
    by_bank = {bank.id: bank for bank in connected_banks(session, registry)}
    params = {k: str(v) for k, v in {"start_date": start_date, "end_date": end_date}.items() if v}
    jobs = [all_transactions(http, session, by_bank[a["institution_id"]], a["id"], params)
            for a in listing["items"] if a["institution_id"] in by_bank]
    results = await asyncio.gather(*jobs, return_exceptions=True)
    items: list[dict] = []
    errors = list(listing["errors"])
    for result in results:
        if isinstance(result, UpstreamError):
            errors.append(failure(result))
        elif isinstance(result, BaseException):
            raise result
        else:
            items.extend(result)
    return {"items": items, "errors": errors}
