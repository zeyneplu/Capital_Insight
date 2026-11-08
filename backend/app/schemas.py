from datetime import datetime, date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    provider: str
    kind: str
    remote_id: str | None
    display_name: str
    expires_at: datetime | None
    created_at: datetime


class CodeRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254, examples=["customer1@chase.example.test"])

    @field_validator("email")
    @classmethod
    def normalize(cls, value: str) -> str:
        value = value.strip().lower()
        if value.count("@") != 1 or not all(value.split("@")):
            raise ValueError("Provide a valid fictional email")
        return value


class VerifyRequest(CodeRequest):
    code: str = Field(pattern=r"^[0-9]{6}$")


class ProviderOut(BaseModel):
    id: str
    name: str
    kind: str
    configured: bool


class ProviderError(BaseModel):
    connection_id: str
    provider: str
    status_code: int
    message: str


class AccountOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    connection_id: str
    provider: str
    source_account_id: str
    account_type: str
    account_name: str
    currency: str | None
    balance: Decimal | None
    balance_kind: Literal["asset", "liability", "unknown"]


class AccountCollection(BaseModel):
    items: list[AccountOut]
    errors: list[ProviderError]
    complete: bool


class ProjectionOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    connection_id: str
    provider: str
    source_record_id: str
    amount: Decimal
    apr: Decimal
    monthly_payment: Decimal
    term_months: int
    status: str
    record_kind: Literal["approval_projection"] = "approval_projection"
    current_balance: None = None


class ProjectionCollection(BaseModel):
    items: list[ProjectionOut]
    errors: list[ProviderError]
    complete: bool


class TransactionOut(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    account_id: str
    source_transaction_id: str
    transaction_date: date
    description: str
    merchant: str | None
    category: str
    amount: Decimal
    direction: Literal["credit", "debit"]


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int


class CurrencySummary(BaseModel):
    currency: str
    assets: Decimal
    liabilities: Decimal
    net_balance: Decimal


class DashboardOut(BaseModel):
    by_currency: list[CurrencySummary]
    account_count: int
    connection_count: int
    excluded_accounts: int
    errors: list[ProviderError]
    complete: bool
    coverage: str


class Message(BaseModel):
    message: str
