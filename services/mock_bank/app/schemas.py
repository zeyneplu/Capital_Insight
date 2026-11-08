from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

AccountType = Literal["checking", "savings", "credit_card", "cd", "ira", "personal_loan", "auto_loan", "mortgage"]
Category = Literal["groceries", "dining", "shopping", "transportation", "utilities", "entertainment", "rent", "healthcare", "education", "salary", "transfers", "debt_payment", "other"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerOut(ORMModel):
    id: str
    first_name: str
    last_name: str
    email: str
    date_of_birth: date
    synthetic_identity_id: str
    created_at: datetime


class BalanceOut(ORMModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "id": "chase-customer-001-checking", "currency": "USD", "balance": "8000.00",
        "updated_at": "2026-11-01T00:00:00Z"}]})
    id: str
    currency: str
    balance: Decimal
    updated_at: datetime


class AccountOut(BalanceOut):
    model_config = ConfigDict(from_attributes=True, json_schema_extra={"examples": [{
        "id": "amex-customer-001-credit_card", "customer_id": "amex-customer-001",
        "institution_id": "amex", "account_type": "credit_card", "account_name": "Mock Credit Card",
        "account_number_last4": "1234", "currency": "USD", "opening_balance": "1000.00",
        "balance": "600.00", "credit_limit": "5000.00", "purchase_apr": "0.1800",
        "minimum_payment": "25.00", "payment_due_date": "2026-11-21",
        "created_at": "2026-08-03T00:00:00Z", "updated_at": "2026-11-01T00:00:00Z",
        "apy": None, "original_principal": None, "outstanding_principal": None,
        "apr": None, "monthly_payment": None, "term_months": None, "maturity_date": None,
        "account_value": None, "account_subtype": None}]})
    customer_id: str
    institution_id: str
    account_type: AccountType
    account_name: str
    account_number_last4: str
    opening_balance: Decimal
    created_at: datetime
    apy: Decimal | None
    credit_limit: Decimal | None
    purchase_apr: Decimal | None
    minimum_payment: Decimal | None
    payment_due_date: date | None
    original_principal: Decimal | None
    outstanding_principal: Decimal | None
    apr: Decimal | None
    monthly_payment: Decimal | None
    term_months: int | None
    maturity_date: date | None
    account_value: Decimal | None
    account_subtype: str | None


class TransactionOut(ORMModel):
    id: str
    account_id: str
    transaction_date: date
    description: str
    merchant: str
    category: Category
    amount: Decimal
    direction: Literal["credit", "debit"]
    transaction_type: str
    created_at: datetime


class TransactionPage(BaseModel):
    items: list[TransactionOut]
    total: int
    limit: int
    offset: int


class EmailRequest(BaseModel):
    email: str = Field(max_length=254, examples=["customer1@chase.example.test"])

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if len(value.split("@")) != 2 or not all(value.split("@")) or "." not in value.split("@")[1]:
            raise ValueError("Provide a valid fictional email address")
        return value


class VerifyRequest(EmailRequest):
    code: str = Field(pattern=r"^[0-9]{6}$", examples=["123456"])


class Message(BaseModel):
    message: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class InstitutionOut(BaseModel):
    id: str
    name: str
    products: list[AccountType]
    synthetic: bool = True


class HealthOut(BaseModel):
    status: str
    bank_id: str
