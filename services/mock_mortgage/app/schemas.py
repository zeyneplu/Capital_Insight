from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    email: str = Field(max_length=254, examples=["customer1@mortgages.example.test"])

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


MortgageType = Literal["mortgage"]

class ApplicationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{
        "mortgage_type": "mortgage", "property_value": "350000.00", "down_payment": "70000.00", "term_months": 360,
        "annual_income": "120000.00", "existing_monthly_debt": "500.00", "credit_score": 740}]})
    mortgage_type: MortgageType = "mortgage"
    property_value: Decimal = Field(gt=0, le=15000000, max_digits=14, decimal_places=2)
    down_payment: Decimal = Field(ge=0, le=15000000, max_digits=14, decimal_places=2)
    term_months: int = Field(ge=1, le=360)
    annual_income: Decimal = Field(gt=0, le=100000000, max_digits=14, decimal_places=2)
    existing_monthly_debt: Decimal = Field(ge=0, le=10000000, max_digits=14, decimal_places=2)
    credit_score: int = Field(ge=300, le=850)

    @model_validator(mode="after")
    def valid_down_payment(self):
        if self.down_payment >= self.property_value:
            raise ValueError("down_payment must be less than property_value")
        return self


class ApplicationOut(ApplicationIn):
    model_config = ConfigDict(from_attributes=True)
    amount: Decimal
    loan_to_value: Decimal
    id: str
    customer_id: str
    apr: Decimal
    monthly_payment: Decimal
    status: Literal["approved", "declined"]
    decision_reason: str
    created_at: datetime
    simulated: bool = True


class Offer(BaseModel):
    mortgage_type: MortgageType
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
    mortgage_types: list[MortgageType]
    synthetic: bool = True
