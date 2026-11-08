"""Sessions and the consent flow (request a code, verify it, disconnect)."""
import time

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..deps import ClientDep, RegistryDep, SessionDep, institution_or_404, store
from ..sessions import Connection
from ..upstream import UpstreamError, as_http, call

router = APIRouter(prefix="/api/v1", tags=["Sessions and connections"])


class EmailIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class VerifyIn(EmailIn):
    code: str = Field(pattern=r"^[0-9]{6}$")


@router.post("/sessions", status_code=201, summary="Start an anonymous Capital Insight session")
def create_session(request: Request) -> dict:
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
async def request_code(institution_id: str, body: EmailIn, session: SessionDep, http: ClientDep, registry: RegistryDep) -> dict:
    institution = institution_or_404(registry, institution_id)
    try:
        return await call(http, institution, "POST", "/v1/auth/request-code", json=body.model_dump())
    except UpstreamError as error:
        raise as_http(error) from error


@router.post("/institutions/{institution_id}/verify-code", summary="Exchange the code for an access token kept on the server")
async def verify_code(institution_id: str, body: VerifyIn, session: SessionDep, http: ClientDep, registry: RegistryDep) -> dict:
    institution = institution_or_404(registry, institution_id)
    try:
        token = await call(http, institution, "POST", "/v1/auth/verify-code", json=body.model_dump())
        customer = await call(http, institution, "GET", "/v1/customers/me", token=token["access_token"])
    except UpstreamError as error:
        raise as_http(error) from error
    # Keep a small safety margin so we never send a token in its last seconds.
    expires_at = time.time() + max(int(token.get("expires_in", 0)) - 30, 0)
    session.connections[institution.id] = Connection(token["access_token"], expires_at, customer)
    return {"institution_id": institution.id, "connected": True, "customer": customer}


@router.delete("/institutions/{institution_id}/connection", status_code=204, summary="Forget this institution's token")
def disconnect(institution_id: str, session: SessionDep, registry: RegistryDep) -> Response:
    if institution_id not in registry:
        raise HTTPException(404, "Institution not found")
    session.connections.pop(institution_id, None)
    return Response(status_code=204)
