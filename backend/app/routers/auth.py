"""Application login; independent of each institution's consent-code login."""

from datetime import datetime, timedelta
import re
import secrets
import hmac
from cryptography.fernet import InvalidToken
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..database import utcnow
from ..dependencies import SessionDep, UserDep
from ..models import SessionToken, User, EmailChallenge
from ..security import hash_password, hash_token, verify_password
from ..mailer import MailDeliveryError, validate_mail_configuration, send_user_code


router = APIRouter(prefix="/v1/auth", tags=["Application authentication"])


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128, repr=False)

    @field_validator("email")
    @classmethod
    def normalized_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", value):
            raise ValueError("Enter a valid email address")
        return value


class RegisterRequest(Credentials):
    password: str = Field(min_length=10, max_length=128, repr=False)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    created_at: datetime
    email_verified_at: datetime | None


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


class EmailCodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize(cls, value):
        return Credentials.normalized_email(value)


class EmailCodeVerify(EmailCodeRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


def lock_email_challenge(session):
    if session.bind.dialect.name == "sqlite":
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")


@router.post("/request-email-code", status_code=202, summary="Send a sign-in code to your own email")
def request_email_code(body: EmailCodeRequest, request: Request, session: SessionDep):
    settings = request.app.state.settings
    try:
        validate_mail_configuration(settings)
    except MailDeliveryError:
        raise HTTPException(503, "Email sign-in requires SMTP credentials in .env.mail") from None
    lock_email_challenge(session)
    prior = session.scalar(select(EmailChallenge).where(EmailChallenge.email == body.email).with_for_update())
    now = utcnow()
    if prior and (now-prior.requested_at).total_seconds() < 30:
        raise HTTPException(429, "Wait before requesting another email", headers={"Retry-After":"30"})
    code = f"{secrets.randbelow(1000000):06}"
    if prior is None:
        prior = EmailChallenge(email=body.email)
        session.add(prior)
    prior.encrypted_code = request.app.state.cipher.encrypt(code.encode()).decode()
    prior.requested_at = now
    prior.expires_at = now+timedelta(minutes=5)
    prior.attempts = 0
    prior.used = False
    try:
        send_user_code(settings, body.email, code, 300)
        session.commit()
    except MailDeliveryError:
        session.rollback()
        raise HTTPException(503, "Could not send email. Check SMTP configuration and try again.") from None
    except IntegrityError:
        session.rollback()
        raise HTTPException(429, "A code was requested concurrently; wait before retrying") from None
    return {"message":"A sign-in code was sent to your email.", "delivery":"email"}


@router.post("/verify-email-code", response_model=TokenResponse, summary="Verify your email and sign in or create an account")
def verify_email_code(body: EmailCodeVerify, request: Request, session: SessionDep):
    lock_email_challenge(session)
    challenge = session.scalar(select(EmailChallenge).where(EmailChallenge.email == body.email).with_for_update())
    if challenge is None or challenge.used or challenge.expires_at <= utcnow() or challenge.attempts >= 5:
        raise HTTPException(401, "Invalid or expired email code")
    challenge.attempts += 1
    try:
        expected = request.app.state.cipher.decrypt(challenge.encrypted_code.encode()).decode()
    except InvalidToken:
        raise HTTPException(401, "Invalid or expired email code") from None
    if not hmac.compare_digest(expected, body.code):
        session.commit()
        raise HTTPException(401, "Invalid or expired email code")
    challenge.used = True
    user = session.scalar(select(User).where(User.email == body.email))
    if user is None:
        user = User(email=body.email, password_hash="!email-only")
        session.add(user)
        session.flush()
    user.email_verified_at = utcnow()
    return new_session(user, request, session)
