from typing import Annotated

import httpx
from fastapi import Depends, Header, HTTPException, Request

from .institutions import Institution
from .sessions import Session, SessionStore
from .upstream import UpstreamError, call
from .dependencies import SessionDep as DatabaseDep, BearerDep, current_user
from .identity import restore_connections


def store(request: Request) -> SessionStore:
    return request.app.state.sessions


def client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


def registry(request: Request) -> dict[str, Institution]:
    return request.app.state.registry


def current_session(
    request: Request,
    database: DatabaseDep,
    credentials: BearerDep,
    x_session_id: Annotated[str | None, Header(max_length=128)] = None,
) -> Session:
    session = store(request).get(x_session_id) if x_session_id else None
    if credentials:
        user = current_user(request, database, credentials)
        if user.email_verified_at is None:
            raise HTTPException(403, "Verify your email before accessing financial connections")
        if session and (session.user_id != user.id or session.auth_session_id != request.state.session_token_id):
            # Never attach one user's adapter cookie to another user's bearer.
            session = None
        if session is None:
            session = store(request).for_auth_session(user.id, request.state.session_token_id)
    if session is None:
        raise HTTPException(401, "Missing or expired session. Create one with POST /api/v1/sessions.")
    if session.user_id:
        restore_connections(session, database, request.app.state.cipher)
    return session


SessionDep = Annotated[Session, Depends(current_session)]
ClientDep = Annotated[httpx.AsyncClient, Depends(client)]
RegistryDep = Annotated[dict[str, Institution], Depends(registry)]


def institution_or_404(registry: dict[str, Institution], institution_id: str, *services: str) -> Institution:
    institution = registry.get(institution_id)
    if institution is None or (services and institution.service not in services):
        raise HTTPException(404, "Institution not found")
    return institution


async def authed_call(http: httpx.AsyncClient, session: Session, institution: Institution, method: str, path: str, **kwargs):
    """Calls a protected route; an upstream 401 means the consent expired, so drop it."""
    connection = session.active(institution.id)
    if connection is None:
        raise UpstreamError(institution.id, 401, f"{institution.name} is not connected")
    try:
        return await call(http, institution, method, path, token=connection.access_token, **kwargs)
    except UpstreamError as error:
        if error.status == 401:
            session.connections.pop(institution.id, None)
            session.revoked.add(institution.id)
        raise
