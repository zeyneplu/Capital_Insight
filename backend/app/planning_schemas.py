from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class PreferencesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ai_enabled: bool = False
    show_forecast: bool = False
    show_subscriptions: bool = False
    show_spending: bool = False
    monthly_income: Decimal | None = Field(default=None,ge=0,le=1000000,decimal_places=2)
    monthly_budget: Decimal | None = Field(default=None,ge=0,le=1000000,decimal_places=2)
    forecast_months: int = Field(default=12,ge=3,le=24)
    stocks_pct: int = Field(default=50,ge=0,le=100)
    bonds_pct: int = Field(default=30,ge=0,le=100)
    cash_pct: int = Field(default=20,ge=0,le=100)

    @model_validator(mode="after")
    def allocation(self):
        if self.stocks_pct+self.bonds_pct+self.cash_pct != 100:
            raise ValueError("Investment scenario allocations must total 100%")
        return self

class GoalIn(BaseModel):
    model_config = ConfigDict(extra="forbid",str_strip_whitespace=True)
    name: str = Field(min_length=1,max_length=100)
    kind: Literal["education","retirement","car","emergency","investment","credit","custom"]
    target_amount: Decimal = Field(default=0,ge=0,le=100000000,decimal_places=2)
    saved_amount: Decimal = Field(default=0,ge=0,le=100000000,decimal_places=2)
    monthly_contribution: Decimal = Field(default=0,ge=0,le=1000000,decimal_places=2)
    months: int = Field(default=12,ge=1,le=600)
    annual_return_pct: Decimal = Field(default=0,ge=0,le=15,decimal_places=2)
    target_score: int | None = Field(default=None,ge=300,le=850)
    target_utilization_pct: int = Field(default=30,ge=1,le=100)
    show_on_dashboard: bool = True

    @model_validator(mode="after")
    def target(self):
        if self.kind=="credit" and self.target_score is None:
            raise ValueError("Choose an aspirational credit-score target")
        if self.kind!="credit" and self.target_amount<=0:
            raise ValueError("Choose a positive savings target")
        return self

class ChatIn(BaseModel):
    model_config = ConfigDict(extra="forbid",str_strip_whitespace=True)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    message: str = Field(min_length=1,max_length=2000)

class SamReply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allowed: bool = True
    answer: str = Field(min_length=1,max_length=7000)
    steps: list[str] = Field(default_factory=list,max_length=8)
    questions: list[str] = Field(default_factory=list,max_length=3)
