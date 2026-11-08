"""Persisted identity shared by the frontend adapter and core connections."""
from fastapi import HTTPException
from sqlalchemy import select
from .database import utcnow
from .models import User, SessionToken, Connection
from .sessions import Connection as LiveConnection


def session_user(live_session, database):
    if not live_session.user_id or not live_session.auth_session_id:
        raise HTTPException(403, "Sign in and verify your own email before linking an institution")
    token = database.get(SessionToken, live_session.auth_session_id)
    user = database.get(User, live_session.user_id)
    if token is None or token.user_id != live_session.user_id or token.expires_at <= utcnow():
        raise HTTPException(401, "Your sign-in expired; sign in again")
    if user is None or user.email_verified_at is None:
        raise HTTPException(403, "Verify your email before connecting accounts")
    return user


def restore_connections(live_session, database, cipher):
    user = session_user(live_session, database)
    links = database.scalars(select(Connection).where(Connection.user_id == user.id,
        Connection.kind.in_(["mock_bank", "mock_loan", "mock_mortgage"]))).all()
    live_session.connections.clear()
    for link in links:
        if link.provider in live_session.revoked:
            continue
        if link.expires_at and link.expires_at <= utcnow():
            continue
        live_session.connections[link.provider] = LiveConnection(
            cipher.decrypt(link.encrypted_token.encode()).decode(),
            link.expires_at.timestamp() if link.expires_at else float("inf"),
            link.customer_profile or {"id":link.remote_id, "email":""})


def recipient_payload(settings, user, body):
    if settings.mock_email_recipient_mode == "customer":
        # Each institution chooses its own registered customer address. No shared key.
        return {key: value for key, value in body.items() if key != "delivery_email"}, None
    if settings.auth_code_delivery != "smtp":
        return body, None
    if settings.mock_service_api_key is None:
        raise HTTPException(503, "Configure MOCK_SERVICE_API_KEY for verified-email institution delivery")
    return {**body, "delivery_email":user.email}, settings.mock_service_api_key.get_secret_value()
