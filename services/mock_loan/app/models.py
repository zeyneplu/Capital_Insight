from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base, UTCDateTime, utcnow


class Metadata(Base):
    __tablename__ = "lender_metadata"
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[str]


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(primary_key=True)
    first_name: Mapped[str]
    last_name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)
    date_of_birth: Mapped[date]
    synthetic_identity_id: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Verification(Base):
    __tablename__ = "verifications"
    email: Mapped[str] = mapped_column(primary_key=True)
    code_hash: Mapped[str]
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(default=0)
    used: Mapped[bool] = mapped_column(default=False)


class LoanApplication(Base):
    __tablename__ = "loan_applications"
    id: Mapped[str] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    loan_type: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    term_months: Mapped[int]
    annual_income: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    existing_monthly_debt: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    credit_score: Mapped[int]
    apr: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    monthly_payment: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    status: Mapped[str]
    decision_reason: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


