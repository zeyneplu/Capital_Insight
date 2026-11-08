"""Request-scoped database access and user/connection authorization."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import utcnow
from .models import Connection, SessionToken, User
from .security import hash_token


bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def current_user(request: Request, session: SessionDep, credentials: BearerDep) -> User:
    invalid = HTTPException(
        status_code=401,
        detail="A valid Capital Insight session is required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise invalid
    record = session.scalar(
        select(SessionToken).where(SessionToken.token_hash == hash_token(credentials.credentials))
    )
    if record is None or record.expires_at <= utcnow():
        raise invalid
    user = session.get(User, record.user_id)
    if user is None:
        raise invalid
    request.state.session_token_id = record.id
    return user


UserDep = Annotated[User, Depends(current_user)]


def owned_connection(connection_id: str, session: SessionDep, user: UserDep) -> Connection:
    if user.email_verified_at is None:
        raise HTTPException(403, "Verify your email before accessing financial connections")
    connection = session.scalar(
        select(Connection).where(Connection.id == connection_id, Connection.user_id == user.id)
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return connection


ConnectionDep = Annotated[Connection, Depends(owned_connection)]


def verified_user(user: UserDep) -> User:
    if user.email_verified_at is None:
        raise HTTPException(403, "Verify your own email before connecting financial accounts")
    return user


VerifiedUserDep = Annotated[User, Depends(verified_user)]
