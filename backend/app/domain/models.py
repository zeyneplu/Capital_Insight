"""Core domain model.

Every data source (Nessie, the PNC generator, demo fixtures) is translated into
these types at the edge of the system. Nothing past the `sources` package ever
sees a raw API payload. That is what lets us add or swap a source without
touching the engine, the agent, or the frontend.

Money is always `Decimal`, never `float`: 0.1 + 0.2 != 0.3 in floating point,
and a finance app that is off by a cent loses the user's trust.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.domain.errors import NotFoundError


class AccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CASH = "cash"  # money the user tracks by hand (wallet, jar)
    CD = "cd"
    IRA = "ira"
    CREDIT_CARD = "credit_card"
    LOAN = "loan"
    MORTGAGE = "mortgage"

    @property
    def is_debt(self) -> bool:
        return self in (AccountType.CREDIT_CARD, AccountType.LOAN, AccountType.MORTGAGE)

    @property
    def is_liquid(self) -> bool:
        """Spendable today without penalties. CDs and IRAs are assets, but locked."""
        return self in (AccountType.CHECKING, AccountType.SAVINGS, AccountType.CASH)


class Account(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    institution: str = Field(examples=["PNC", "Capital One"])
    type: AccountType
    nickname: str
    balance: Decimal = Field(
        description="Cash held for deposit accounts; amount owed (positive) for debt accounts.",
        ge=0,
    )
    annual_rate: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        description="As a fraction (0.18 = 18%). APY for deposit accounts, APR for debt.",
    )
    credit_limit: Decimal | None = Field(
        default=None,
        gt=0,
        description="Credit cards only. None when the source does not provide it (e.g. Nessie).",
    )


class Transaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    account_id: str
    posted_on: date
    amount: Decimal = Field(description="Negative = money out of the account.")
    description: str
    category: str


class FinancialProfile(BaseModel):
    """One person's whole financial picture, across every institution."""

    model_config = ConfigDict(frozen=True)

    customer_id: str
    display_name: str
    accounts: tuple[Account, ...]
    monthly_income: Decimal | None = Field(default=None, ge=0)
    monthly_expenses: Decimal | None = Field(default=None, ge=0)
    credit_score: int | None = Field(
        default=None,
        ge=300,
        le=850,
        description="Sandbox value (e.g. from Nessie loans), not a live credit-bureau score.",
    )

    def account(self, account_id: str) -> Account:
        for acct in self.accounts:
            if acct.id == account_id:
                return acct
        raise NotFoundError(f"Account {account_id!r} not found")
