"""HTTP routes. Flow for an app that wants a customer's data (like Plaid or Zelle would):

  1. POST /v1/consents                     {email, ssn_last4}  -> consent_id  (bank emails a code)
  2. POST /v1/consents/{consent_id}/token  {code}              -> access_token
  3. GET  /v1/accounts                     Authorization: Bearer <access_token>
  4. GET  /v1/accounts/{id}/transactions   Authorization: Bearer <access_token>

Try it in the browser at http://localhost:<port>/docs (click "Authorize" after step 2).
"""

from collections.abc import Iterator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from mockbank import security
from mockbank.config import Settings
from mockbank.models import AccessToken, Account, Consent, Customer, OutboxMessage, Transaction
from mockbank.schemas import (
    AccountList,
    AccountOut,
    BankInfo,
    ConsentRequest,
    ConsentResponse,
    OutboxItem,
    TokenRequest,
    TokenResponse,
    TransactionList,
    TransactionOut,
    bps,
    cents,
)

router = APIRouter()
dev_router = APIRouter(prefix="/dev", tags=["dev only"])

# One message for every failure, so attackers can't tell "wrong code" from "no such consent".
INVALID_CODE = "Invalid or expired code. Start a new connection if this keeps happening."


# --- dependencies ---------------------------------------------------------------


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessionmaker() as session:
        yield session


Db = Annotated[Session, Depends(get_db)]
Config = Annotated[Settings, Depends(get_settings)]
_bearer = HTTPBearer(auto_error=False)


def current_customer_id(
    db: Db,
    settings: Config,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing, invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    secret = settings.bank_secret.get_secret_value()
    row = db.get(AccessToken, security.digest(secret, credentials.credentials))
    if row is None or row.expires_at <= security.now():
        raise unauthorized
    return row.customer_id


CustomerId = Annotated[str, Depends(current_customer_id)]


# --- public routes ----------------------------------------------------------------


@router.get("/health")
def health(settings: Config) -> dict[str, str]:
    return {"status": "ok", "bank_id": settings.bank_id}


@router.get("/v1/bank")
def bank_info(settings: Config) -> BankInfo:
    return BankInfo(bank_id=settings.bank_id, name=settings.bank_name)


@router.post("/v1/consents", status_code=status.HTTP_202_ACCEPTED)
def start_consent(body: ConsentRequest, db: Db, settings: Config) -> ConsentResponse:
    """Always answers 202 with the same message, match or not, so this endpoint can't be
    used to discover who banks here (no "user enumeration")."""
    customer = db.scalar(select(Customer).where(Customer.email == body.email.lower()))
    matched = customer is not None and security.same(customer.ssn_last4, body.ssn_last4)
    consent_id = security.new_id()
    code = security.new_code()
    ttl = settings.otp_ttl_minutes * 60
    db.add(
        Consent(
            id=consent_id,
            customer_id=customer.id if matched else None,
            code_hash=security.digest(
                settings.bank_secret.get_secret_value(), f"{consent_id}:{code}"
            ),
            expires_at=security.now() + ttl,
        )
    )
    if matched:
        db.add(
            OutboxMessage(
                to_email=customer.email,
                body=f"Your {settings.bank_name} code is {code}. "
                f"It expires in {settings.otp_ttl_minutes} minutes. Never share it.",
                created_at=security.now(),
            )
        )
    db.commit()
    return ConsentResponse(consent_id=consent_id, expires_in_seconds=ttl)


@router.post("/v1/consents/{consent_id}/token")
def exchange_code(consent_id: str, body: TokenRequest, db: Db, settings: Config) -> TokenResponse:
    secret = settings.bank_secret.get_secret_value()
    consent = db.get(Consent, consent_id)
    if consent is None or consent.used or consent.expires_at <= security.now():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)
    if consent.attempts >= settings.otp_max_attempts:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts. Start again.")

    consent.attempts += 1
    valid = consent.customer_id is not None and security.matches(
        secret, f"{consent_id}:{body.code}", consent.code_hash
    )
    if not valid:
        db.commit()  # persist the failed attempt before refusing
        raise HTTPException(status.HTTP_400_BAD_REQUEST, INVALID_CODE)

    consent.used = True  # codes are single-use
    token = security.new_token()
    ttl = settings.token_ttl_minutes * 60
    db.add(
        AccessToken(
            token_hash=security.digest(secret, token),
            customer_id=consent.customer_id,
            expires_at=security.now() + ttl,
        )
    )
    db.commit()
    return TokenResponse(access_token=token, expires_in_seconds=ttl)


@router.get("/v1/accounts")
def list_accounts(customer_id: CustomerId, db: Db) -> AccountList:
    rows = db.scalars(
        select(Account).where(Account.customer_id == customer_id).order_by(Account.id)
    )
    return AccountList(
        accounts=[
            AccountOut(
                id=a.id,
                type=a.type,
                nickname=a.nickname,
                mask=a.mask,
                balance=cents(a.balance_cents),
                annual_rate=bps(a.rate_bps),
                credit_limit=cents(a.credit_limit_cents) if a.credit_limit_cents else None,
            )
            for a in rows
        ]
    )


@router.get("/v1/accounts/{account_id}/transactions")
def list_transactions(
    account_id: str,
    customer_id: CustomerId,
    db: Db,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> TransactionList:
    account = db.get(Account, account_id)
    # 404 (not 403) for someone else's account: don't confirm that it exists.
    if account is None or account.customer_id != customer_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Account not found")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date is after end_date")

    query = select(Transaction).where(Transaction.account_id == account_id)
    if start_date:
        query = query.where(Transaction.posted_on >= start_date)
    if end_date:
        query = query.where(Transaction.posted_on <= end_date)
    rows = db.scalars(query.order_by(Transaction.posted_on.desc(), Transaction.id))
    return TransactionList(
        transactions=[
            TransactionOut(
                id=t.id,
                account_id=t.account_id,
                posted_on=t.posted_on,
                amount=cents(t.amount_cents),
                description=t.description,
                category=t.category,
            )
            for t in rows
        ]
    )


# --- dev only: a fake inbox, so the demo needs no email server ------------------------


@dev_router.get("/outbox")
def read_outbox(db: Db, email: str | None = None) -> list[OutboxItem]:
    query = select(OutboxMessage).order_by(OutboxMessage.id.desc()).limit(20)
    if email:
        query = query.where(OutboxMessage.to_email == email.strip().lower())
    return [OutboxItem(to=m.to_email, body=m.body, sent_at=m.created_at) for m in db.scalars(query)]
