import hmac
import logging
import secrets
from datetime import timedelta
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from ..database import utcnow
from ..dependencies import SessionDep
from ..models import Customer, Verification
from ..schemas import EmailRequest, VerifyRequest, Message, TokenOut
from ..security import digest, issue_token

router = APIRouter(prefix="/v1/auth", tags=["Mock authorization"])
logger = logging.getLogger("uvicorn.error")


@router.post("/request-code", response_model=Message, status_code=202,
             responses={429: {"description": "Request cooldown active"}},
             summary="Request mock consent code", description="Codes appear only in server logs when DEMO_MODE=true. Never sends email. Responses do not disclose customer registration.")
def request_code(body: EmailRequest, request: Request, session: SessionDep):
    settings = request.app.state.settings
    # Serialize read/modify/write across SQLite connections and worker processes.
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    now = utcnow()
    prior = session.get(Verification, body.email)
    if prior and (now-prior.requested_at).total_seconds() < settings.request_cooldown_seconds:
        raise HTTPException(429, "Please wait before requesting another code", headers={"Retry-After": str(settings.request_cooldown_seconds)})
    code = f"{secrets.randbelow(1000000):06}"
    if prior is None:
        prior = Verification(email=body.email)
        session.add(prior)
    prior.code_hash = digest(request.app.state.secret, body.email+":"+code)
    prior.requested_at = now
    prior.expires_at = now+timedelta(seconds=settings.code_ttl_seconds)
    prior.attempts = 0
    prior.used = False
    customer = session.scalar(select(Customer).where(Customer.email == body.email))
    session.commit()
    if settings.demo_mode and customer:
        logger.warning("DEVELOPMENT ONLY mock consent code for %s: %s", body.email, code)
    return {"message": "If registered, a mock code was generated. Demo mode exposes it only in development server logs."}


@router.post("/verify-code", response_model=TokenOut, responses={401: {"description": "Invalid, expired, exhausted or used code"}},
             summary="Exchange a one-time mock code for a signed bearer token")
def verify_code(body: VerifyRequest, request: Request, session: SessionDep):
    settings = request.app.state.settings
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    record = session.get(Verification, body.email)
    if record is None or record.used or record.expires_at <= utcnow() or record.attempts >= settings.code_attempt_limit:
        raise HTTPException(401, "Invalid or expired verification code")
    record.attempts += 1
    valid = hmac.compare_digest(record.code_hash, digest(request.app.state.secret, body.email+":"+body.code))
    customer = session.scalar(select(Customer).where(Customer.email == body.email))
    if not valid or customer is None:
        session.commit()
        raise HTTPException(401, "Invalid or expired verification code")
    record.used = True
    session.commit()
    return {"access_token": issue_token(request.app.state.secret, settings.lender_id, customer.id, settings.token_ttl_seconds),
            "expires_in": settings.token_ttl_seconds}
