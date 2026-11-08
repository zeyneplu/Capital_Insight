"""Application login; independent of each institution's consent-code login."""

from datetime import datetime, timedelta
import re
import secrets
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..database import utcnow
from ..dependencies import SessionDep, UserDep
from ..models import SessionToken, User
from ..security import hash_password, hash_token, verify_password


router = APIRouter(prefix="/v1/auth", tags=["Application authentication"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class RegisterRequest(Credentials):
    password: str = Field(min_length=10, max_length=128, repr=False)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserResponse


def new_session(user: User, request: Request, session: SessionDep) -> TokenResponse:
    ttl = request.app.state.settings.session_ttl_seconds
    token = secrets.token_urlsafe(32)
    session.add(
        SessionToken(user_id=user.id, token_hash=hash_token(token),
                     expires_at=utcnow() + timedelta(seconds=ttl))
    )
    session.commit()
    return TokenResponse(access_token=token, expires_in=ttl, user=UserResponse.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, session: SessionDep):
    user = User(email=payload.email, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from None
    return new_session(user, request, session)


@router.post("/login", response_model=TokenResponse)
def login(payload: Credentials, request: Request, session: SessionDep):
    user = session.scalar(select(User).where(User.email == payload.email))
    # Run the same expensive operation for unknown emails to reduce timing leakage.
    verified = verify_password(payload.password, user.password_hash) if user else False
    if user is None:
        hash_password(payload.password)
    if not verified:
        raise HTTPException(status_code=401, detail="Email or password is incorrect",
                            headers={"WWW-Authenticate": "Bearer"})
    return new_session(user, request, session)


@router.get("/me", response_model=UserResponse)
def me(user: UserDep):
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, user: UserDep, session: SessionDep):
    record = session.get(SessionToken, request.state.session_token_id)
    if record is not None:
        session.delete(record)
        session.commit()
    return Response(status_code=204)
