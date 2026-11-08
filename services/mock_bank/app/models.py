from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, ForeignKey, Numeric, CheckConstraint, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base, UTCDateTime, utcnow


from .credit import customer_score_default


class Metadata(Base):
    __tablename__ = "bank_metadata"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (CheckConstraint("credit_score BETWEEN 300 AND 850"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    first_name: Mapped[str]
    last_name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    date_of_birth: Mapped[date]
    synthetic_identity_id: Mapped[str] = mapped_column(unique=True)
    credit_score: Mapped[int] = mapped_column(default=customer_score_default)
    credit_score_as_of: Mapped[date] = mapped_column(default=date.today)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (CheckConstraint("balance >= 0"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    institution_id: Mapped[str]
    account_type: Mapped[str]
    account_name: Mapped[str]
    account_number_last4: Mapped[str] = mapped_column(String(4))
    currency: Mapped[str] = mapped_column(default="USD")
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    apy: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    purchase_apr: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    minimum_payment: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    payment_due_date: Mapped[date | None]
    original_principal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    outstanding_principal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    apr: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int | None]
    maturity_date: Mapped[date | None]
    account_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    account_subtype: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (CheckConstraint("amount >= 0"), CheckConstraint("direction IN ('credit', 'debit')"))
    id: Mapped[str] = mapped_column(primary_key=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    transaction_date: Mapped[date] = mapped_column(index=True)
    description: Mapped[str]
    merchant: Mapped[str]
    category: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    direction: Mapped[str]
    transaction_type: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Verification(Base):
    __tablename__ = "verifications"
    email: Mapped[str] = mapped_column(primary_key=True)
    code_hash: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(default=0)
    used: Mapped[bool] = mapped_column(default=False)


class Posting(Base):
    __tablename__ = "postings"
    __table_args__ = (UniqueConstraint("customer_id", "request_id", name="uq_posting_customer_request"),)
    id: Mapped[str] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    request_id: Mapped[str]
    fingerprint: Mapped[str]
    transaction_ids: Mapped[list[str]] = mapped_column(JSON)
