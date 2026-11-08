import hmac
import logging
import secrets
from datetime import timedelta
from fastapi import APIRouter, Request, HTTPException, Header
from sqlalchemy import select
from ..database import utcnow
from ..dependencies import SessionDep
from ..models import Customer, Verification
from ..schemas import EmailRequest, VerifyRequest, Message, TokenOut
from ..security import digest, issue_token
from ..mail import MailDeliveryError, validate_mail_configuration, send_verification_email

router = APIRouter(prefix="/v1/auth", tags=["Mock authorization"])
logger = logging.getLogger("uvicorn.error")


@router.post("/request-code", response_model=Message, status_code=202,
             responses={429: {"description": "Request cooldown active"}},
             summary="Request mock consent code", description="Email codes to the registered institution customer with AUTH_CODE_DELIVERY=smtp, or development logs in log mode. Codes never appear in responses.")
def request_code(body: EmailRequest, request: Request, session: SessionDep, x_internal_key: str | None = Header(default=None)):
    settings = request.app.state.settings
    delivery_settings = settings
    if body.delivery_email is not None:
        if settings.mock_email_recipient_mode != "forwarded_demo":
            raise HTTPException(403, "Recipient overrides are disabled; codes go to the institution customer email")
        key = settings.mock_service_api_key
        if key is None or x_internal_key is None or not hmac.compare_digest(key.get_secret_value(), x_internal_key):
            raise HTTPException(403, "Only the core API can select a verified email recipient")
        delivery_settings = settings.model_copy(update={"auth_email_recipient": body.delivery_email})
    # Serialize read/modify/write across SQLite connections and worker processes.
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    now = utcnow()
    prior = session.get(Verification, body.email)
    if prior and (now-prior.requested_at).total_seconds() < settings.request_cooldown_seconds:
        raise HTTPException(429, "Please wait before requesting another code", headers={"Retry-After": str(settings.request_cooldown_seconds)})
    code = f"{secrets.randbelow(1000000):06}"
    tester = bool(settings.demo_mode and settings.tester_email and settings.tester_code
                  and body.email == settings.tester_email.strip().lower())
    if tester:
        # Fixed code for the documented tester account only; expiry, attempts and single use still apply.
        code = settings.tester_code
    if prior is None:
        prior = Verification(email=body.email)
        session.add(prior)
    prior.code_hash = digest(request.app.state.secret, body.email+":"+code)
    prior.requested_at = now
    prior.expires_at = now+timedelta(seconds=settings.code_ttl_seconds)
    prior.attempts = 0
    prior.used = False
    customer = session.scalar(select(Customer).where(Customer.email == body.email))
    if settings.auth_code_delivery == "smtp" and customer and not tester:
        if settings.mock_email_recipient_mode == "customer":
            delivery_settings = settings.model_copy(update={"auth_email_recipient": customer.email})
        try:
            validate_mail_configuration(delivery_settings)
        except MailDeliveryError:
            session.rollback()
            raise HTTPException(503, "Email delivery is not configured; check this service's SMTP settings") from None
        try:
            send_verification_email(delivery_settings, code, body.email, settings.bank_name, settings.code_ttl_seconds)
        except MailDeliveryError:
            # A failed send must not activate a new challenge or consume cooldown.
            session.rollback()
            raise HTTPException(503, "Could not send the verification email. Check the mail configuration and try again.") from None
    session.commit()
    if tester:
        return {"message": "Tester account: enter the tester code.", "delivery": "tester"}
    if settings.auth_code_delivery == "smtp":
        return {"message": "If registered, a verification code was emailed to the registered customer address.", "delivery": "email"}
    if settings.demo_mode and customer:
        logger.warning("DEVELOPMENT ONLY mock consent code for %s: %s", body.email, code)
    return {"message": "If registered, a mock code was generated. Demo mode exposes it only in development server logs.", "delivery": "server_log"}


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
    tester = bool(settings.demo_mode and settings.tester_email and settings.tester_code
                  and body.email == settings.tester_email.strip().lower())
    ttl = settings.tester_token_ttl_seconds if tester else settings.token_ttl_seconds
    return {"access_token": issue_token(request.app.state.secret, settings.bank_id, customer.id, ttl),
            "expires_in": ttl}
