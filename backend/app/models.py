"""Application-owned users, institution connections, and Plaid import state."""

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import ForeignKey, JSON, String, Text, UniqueConstraint, CheckConstraint, Numeric
from decimal import Decimal
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base, UTCDateTime, utcnow


def new_id() -> str:
    return str(uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SessionToken(Base):
    __tablename__ = "session_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class CreditProfile(Base):
    """One current score per app user, sourced only from authorized mock banks."""
    __tablename__ = "credit_profiles"
    __table_args__ = (CheckConstraint("score BETWEEN 300 AND 850"),)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[int]
    model: Mapped[str]
    as_of: Mapped[date]


class Connection(Base):
    __tablename__ = "connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", "remote_id", name="uq_connection_remote"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    remote_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str] = mapped_column(String(255))
    customer_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    encrypted_token: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class CachedTransaction(Base):
    __tablename__ = "cached_transactions"
    __table_args__ = (
        UniqueConstraint("connection_id", "remote_id", name="uq_transaction_remote"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), index=True
    )
    remote_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)


class PlaidState(Base):
    __tablename__ = "plaid_states"

    connection_id: Mapped[str] = mapped_column(
        ForeignKey("connections.id", ondelete="CASCADE"), primary_key=True
    )
    cursor: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmailChallenge(Base):
    # Email is the natural primary key of the verification identity.
    __tablename__ = "email_challenges"
    email: Mapped[str] = mapped_column(String(254), primary_key=True)
    encrypted_code: Mapped[str] = mapped_column(Text)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    attempts: Mapped[int] = mapped_column(default=0)
    used: Mapped[bool] = mapped_column(default=False)


class PlanningPreferences(Base):
    __tablename__ = "planning_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON)


class FinancialGoal(Base):
    __tablename__ = "financial_goals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(24))
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON)
    ai_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class SamTurn(Base):
    __tablename__ = "sam_turns"
    __table_args__ = (UniqueConstraint("user_id","request_id",name="uq_sam_user_request"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    request_id: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    response: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
