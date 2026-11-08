"""Database tables.

Money is stored as integer cents and rates as integer basis points (1800 = 18.00%).
Integers are exact on every database, including SQLite, which has no real decimal type.
Times are stored as Unix epoch seconds for the same portability reason.
"""

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mockbank.db import Base


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    # Data minimization: the bank only needs the last 4 digits to verify identity.
    ssn_last4: Mapped[str] = mapped_column(String(4))


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    nickname: Mapped[str] = mapped_column(String(80))
    mask: Mapped[str] = mapped_column(String(4))  # last 4 of the account number
    balance_cents: Mapped[int] = mapped_column(BigInteger)
    rate_bps: Mapped[int] = mapped_column(Integer, default=0)
    credit_limit_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    posted_on: Mapped[date] = mapped_column(Date, index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)  # negative = money out
    description: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40))


class Consent(Base):
    """One "connect my bank" attempt. The code itself is never stored, only its HMAC."""

    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # None = no match
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[int] = mapped_column(BigInteger)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class AccessToken(Base):
    __tablename__ = "access_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(36), index=True)
    expires_at: Mapped[int] = mapped_column(BigInteger)


class OutboxMessage(Base):
    """Stand-in for an email server: messages the bank 'sent'. Swap for AWS SES later."""

    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    to_email: Mapped[str] = mapped_column(String(254), index=True)
    body: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[int] = mapped_column(BigInteger)
