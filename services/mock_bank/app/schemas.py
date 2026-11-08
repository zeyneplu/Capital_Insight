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
    id: str
    currency: str
    balance: Decimal
    updated_at: datetime


class AccountOut(BalanceOut):
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
