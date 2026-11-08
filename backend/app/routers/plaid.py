"""Authenticated Plaid Link, Sandbox, and transaction synchronization endpoints."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..dependencies import ConnectionDep, SessionDep, VerifiedUserDep
from ..models import CachedTransaction, Connection, PlaidState
from ..plaid import access_token_for, client_for, get_accounts, require_plaid, sync_transactions
from ..schemas import AccountOut, ConnectionOut, TransactionPage

router = APIRouter(prefix="/v1/plaid", tags=["Plaid"])


class PublicTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    public_token: str = Field(min_length=1, max_length=2048)


class SandboxTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    institution_id: str = Field(default="ins_109508", min_length=1, max_length=200)


class LinkTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    connection_id: str | None = None


class LinkTokenOut(BaseModel):
    link_token: str
    expiration: datetime


class PublicTokenOut(BaseModel):
    public_token: str


class SyncOut(BaseModel):
    added: int = Field(ge=0)
    modified: int = Field(ge=0)
    removed: int = Field(ge=0)


def connection_response(connection: Connection) -> dict:
    return {
        "id": connection.id,
        "provider": connection.provider,
        "kind": connection.kind,
        "remote_id": connection.remote_id,
        "display_name": connection.display_name,
        "created_at": connection.created_at,
        "expires_at": connection.expires_at,
    }


@router.post("/link-token", response_model=LinkTokenOut)
async def create_link_token(request: Request, session: SessionDep, user: VerifiedUserDep, body: LinkTokenRequest | None = None):
    settings = request.app.state.settings
    payload = {
        "user": {"client_user_id": user.id},
        "client_name": "Capital Insight",
        "products": settings.plaid_products,
        "country_codes": settings.plaid_country_codes,
        "language": "en",
    }
    if settings.plaid_redirect_uri:
        payload["redirect_uri"] = settings.plaid_redirect_uri
    if body and body.connection_id:
        connection = session.scalar(select(Connection).where(
            Connection.id == body.connection_id, Connection.user_id == user.id,
        ))
        if connection is None:
            raise HTTPException(404, detail="Connection not found.")
        payload["access_token"] = access_token_for(request, connection)
        # Existing Items enter Link update mode using their server-side token.
        payload.pop("products")
    result = await client_for(request).call("/link/token/create", payload)
    try:
        return {"link_token": result["link_token"], "expiration": result["expiration"]}
    except KeyError:
        raise HTTPException(502, detail="Invalid Plaid Link response.") from None


@router.post("/sandbox/public-token", response_model=PublicTokenOut)
async def create_sandbox_public_token(body: SandboxTokenRequest, request: Request, user: VerifiedUserDep):
    settings = request.app.state.settings
    if settings.plaid_environment != "sandbox":
        raise HTTPException(404, detail="Sandbox endpoint is unavailable.")
    result = await client_for(request).call("/sandbox/public_token/create", {
        "institution_id": body.institution_id,
        "initial_products": settings.plaid_products,
    })
    try:
        return {"public_token": result["public_token"]}
    except KeyError:
        raise HTTPException(502, detail="Invalid Plaid Sandbox response.") from None


@router.post("/exchange-public-token", status_code=201, response_model=ConnectionOut)
async def exchange_public_token(body: PublicTokenRequest, request: Request, session: SessionDep, user: VerifiedUserDep):
    result = await client_for(request).call("/item/public_token/exchange", {"public_token": body.public_token})
    if not isinstance(result.get("access_token"), str) or not isinstance(result.get("item_id"), str):
        raise HTTPException(502, detail="Invalid Plaid exchange response.")
    # The access token belongs only in encrypted server-side storage. It is never
    # returned to a browser or written to logs.
    connection = session.scalar(select(Connection).where(
        Connection.user_id == user.id,
        Connection.provider == "plaid",
        Connection.remote_id == result["item_id"],
    ))
    encrypted_token = request.app.state.cipher.encrypt(result["access_token"].encode()).decode()
    if connection is None:
        connection = Connection(
            user_id=user.id,
            provider="plaid",
            kind="plaid",
            remote_id=result["item_id"],
            display_name="Plaid institution",
            encrypted_token=encrypted_token,
        )
        session.add(connection)
    else:
        connection.encrypted_token = encrypted_token
    try:
        session.flush()
        if session.get(PlaidState, connection.id) is None:
            session.add(PlaidState(connection_id=connection.id, cursor=None))
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, detail="This Plaid Item was connected concurrently. Reload your connections.") from None
    session.refresh(connection)
    return connection_response(connection)


@router.get("/connections/{connection_id}/accounts", response_model=list[AccountOut])
async def accounts(request: Request, connection: ConnectionDep):
    return await get_accounts(request, connection)


@router.post("/connections/{connection_id}/sync", response_model=SyncOut)
async def sync(request: Request, session: SessionDep, connection: ConnectionDep):
    return await sync_transactions(request, session, connection)


@router.get("/connections/{connection_id}/transactions", response_model=TransactionPage)
def transactions(
    session: SessionDep,
    connection: ConnectionDep,
    account_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    require_plaid(connection)
    # Cached payloads use composite IDs to prevent account collisions between Items.
    # Accept both composite IDs from /accounts and original Plaid IDs for convenience.
    composite_id = account_id
    if account_id is not None and not account_id.startswith(f"{connection.id}:"):
        composite_id = f"{connection.id}:{account_id}"
    rows = session.scalars(select(CachedTransaction).where(CachedTransaction.connection_id == connection.id))
    items = [row.payload for row in rows if composite_id is None or row.payload.get("account_id") == composite_id]
    items.sort(key=lambda row: (row.get("transaction_date", ""), row["id"]), reverse=True)
    return {"items": items[offset:offset + limit], "total": len(items), "limit": limit, "offset": offset}
