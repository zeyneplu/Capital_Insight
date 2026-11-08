from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

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


LoanType = Literal["personal_loan", "auto_loan", "mortgage"]

class ApplicationIn(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"loan_type": "personal_loan", "amount": "10000.00", "term_months": 36,
        "annual_income": "72000.00", "existing_monthly_debt": "300.00", "credit_score": 720}]})
    loan_type: LoanType
    amount: Decimal = Field(gt=0, le=750000, max_digits=14, decimal_places=2)
    term_months: int = Field(ge=1, le=360)
    annual_income: Decimal = Field(gt=0, le=100000000, max_digits=14, decimal_places=2)
    existing_monthly_debt: Decimal = Field(ge=0, le=10000000, max_digits=14, decimal_places=2)
    credit_score: int = Field(ge=300, le=850)


class ApplicationOut(ApplicationIn):
    model_config = ConfigDict(from_attributes=True)
    id: str
    customer_id: str
    apr: Decimal
    monthly_payment: Decimal
    status: Literal["approved", "declined"]
    decision_reason: str
    created_at: datetime
    simulated: bool = True


class Offer(BaseModel):
    loan_type: LoanType
    name: str
    minimum_amount: Decimal
    maximum_amount: Decimal
    apr: Decimal
    terms_months: list[int]
    currency: str = "USD"
    simulated: bool = True


class Installment(BaseModel):
    installment: int
    due_date: date
    payment: Decimal
    principal: Decimal
    interest: Decimal
    remaining_balance: Decimal


class HealthOut(BaseModel):
    status: str
    lender_id: str


class LenderOut(BaseModel):
    id: str
    name: str
    loan_types: list[LoanType]
    synthetic: bool = True
