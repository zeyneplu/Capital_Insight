"""The bank's public API contract (request and response bodies).

Every mock bank speaks this same, simplified FDX-style shape (FDX is the US open
banking API standard). Capital Insight therefore needs ONE client for all of them.
Money and rates leave the API as decimal strings ("600.00", "0.1800"), never floats.
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import AfterValidator, BaseModel, EmailStr, Field

from mockbank.validators import validate_ssn_last4


def cents(value: int) -> Decimal:
    return Decimal(value).scaleb(-2)


def bps(value: int) -> Decimal:
    return Decimal(value).scaleb(-4)


class BankInfo(BaseModel):
    bank_id: str
    name: str
    api_version: str = "1"


class ConsentRequest(BaseModel):
    email: EmailStr
    ssn_last4: Annotated[str, AfterValidator(validate_ssn_last4)]


class ConsentResponse(BaseModel):
    consent_id: str
    expires_in_seconds: int
    message: str = "If these details match an account holder, we emailed them a 6-digit code."


class TokenRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$", examples=["123456"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class AccountOut(BaseModel):
    id: str
    type: str = Field(
        examples=["checking", "savings", "credit_card", "loan", "mortgage", "cd", "ira"]
    )
    nickname: str
    mask: str
    currency: str = "USD"
    balance: Decimal = Field(description="Cash held; for debt accounts, amount owed.")
    annual_rate: Decimal = Field(description="APY for deposits, APR for debt, as a fraction.")
    credit_limit: Decimal | None = None


class AccountList(BaseModel):
    accounts: list[AccountOut]


class TransactionOut(BaseModel):
    id: str
    account_id: str
    posted_on: date
    amount: Decimal = Field(description="Negative = money out of the account.")
    description: str
    category: str


class TransactionList(BaseModel):
    transactions: list[TransactionOut]


class OutboxItem(BaseModel):
    to: str
    body: str
    sent_at: int
