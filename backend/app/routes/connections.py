"""Sessions and the consent flow (request a code, verify it, disconnect)."""
import time
from datetime import timedelta
from sqlalchemy import select, delete

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..deps import ClientDep, RegistryDep, SessionDep, institution_or_404, store
from ..sessions import Connection
from ..dependencies import SessionDep as DatabaseDep, BearerDep, current_user
from ..identity import session_user, recipient_payload
from ..models import Connection as SavedConnection
from ..database import utcnow
from ..upstream import UpstreamError, as_http, call

router = APIRouter(prefix="/api/v1", tags=["Sessions and connections"])


class EmailIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class VerifyIn(EmailIn):
    code: str = Field(pattern=r"^[0-9]{6}$")


@router.post("/sessions", status_code=201, summary="Start a frontend session; a verified bearer token enables connections")
def create_session(request: Request, database: DatabaseDep, credentials: BearerDep) -> dict:
    if credentials:
        user = current_user(request, database, credentials)
        if user.email_verified_at is None:
            raise HTTPException(403, "Verify your own email first")
        return {"session_id":store(request).create(user.id, request.state.session_token_id).id}
    return {"session_id": store(request).create().id}


@router.get("/institutions", summary="Institutions and this session's connection status")
def institutions(session: SessionDep, registry: RegistryDep) -> list[dict]:
    result = []
    for institution in registry.values():
        connection = session.active(institution.id)
        result.append({
            "id": institution.id,
            "name": institution.name,
            "service": institution.service,
            "connected": connection is not None,
            "customer": connection.customer if connection else None,
        })
    return result


@router.post("/institutions/{institution_id}/request-code", status_code=202, summary="Ask the institution for a consent code")
async def request_code(institution_id: str, body: EmailIn, request: Request, database: DatabaseDep, session: SessionDep, http: ClientDep, registry: RegistryDep) -> dict:
    institution = institution_or_404(registry, institution_id)
    user = session_user(session, database)
    payload, key = recipient_payload(request.app.state.settings, user, body.model_dump())
    try:
        return await call(http, institution, "POST", "/v1/auth/request-code", json=payload, internal_key=key)
    except UpstreamError as error:
        raise as_http(error) from error


@router.post("/institutions/{institution_id}/verify-code", summary="Exchange the code for an access token kept on the server")
async def verify_code(institution_id: str, body: VerifyIn, request: Request, database: DatabaseDep, session: SessionDep, http: ClientDep, registry: RegistryDep) -> dict:
    institution = institution_or_404(registry, institution_id)
    user = session_user(session, database)
    try:
        token = await call(http, institution, "POST", "/v1/auth/verify-code", json=body.model_dump())
        customer = await call(http, institution, "GET", "/v1/customers/me", token=token["access_token"])
    except UpstreamError as error:
        raise as_http(error) from error
    # Keep a small safety margin so we never send a token in its last seconds.
    expires_at = time.time() + max(int(token.get("expires_in", 0)) - 30, 0)
    session.revoked.discard(institution.id)
    session.connections[institution.id] = Connection(token["access_token"], expires_at, customer)
    saved = database.scalar(select(SavedConnection).where(SavedConnection.user_id == user.id,
        SavedConnection.provider == institution.id, SavedConnection.remote_id == customer["id"]))
    if saved is None:
        saved = SavedConnection(user_id=user.id, provider=institution.id, kind=institution.service,
            remote_id=customer["id"], display_name=institution.name)
        database.add(saved)
    saved.customer_profile = customer
    saved.encrypted_token = request.app.state.cipher.encrypt(token["access_token"].encode()).decode()
    saved.expires_at = utcnow()+timedelta(seconds=max(int(token.get("expires_in",0))-30,0))
    database.commit()
    return {"institution_id": institution.id, "connected": True, "customer": customer}


@router.delete("/institutions/{institution_id}/connection", status_code=204, summary="Forget this institution's token")
def disconnect(institution_id: str, database: DatabaseDep, session: SessionDep, registry: RegistryDep) -> Response:
    if institution_id not in registry:
        raise HTTPException(404, "Institution not found")
    user = session_user(session, database)
    database.execute(delete(SavedConnection).where(SavedConnection.user_id == user.id, SavedConnection.provider == institution_id))
    database.commit()
    session.connections.pop(institution_id, None)
    return Response(status_code=204)
