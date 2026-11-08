"""Tools the AI coach can call. Each one wraps a pure engine function.

Security by design: the registry is built for ONE customer's profile on the server.
No tool takes a customer_id argument, so no prompt (or prompt injection) can make
the model read someone else's data. Authorization lives in code, never in prompts.

Tool arguments are Pydantic models, so the JSON schema sent to the model and the
validation of what comes back are generated from the same definition.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.domain.errors import DomainError
from app.domain.models import FinancialProfile
from app.engine import indicators, planner


class NoArgs(BaseModel):
    pass


class PlanUtilizationArgs(BaseModel):
    account_id: str = Field(description="ID of the credit card account, from get_accounts.")
    target_utilization_percent: float = Field(
        ge=0, lt=100, description="Goal utilization in percent, e.g. 10 for 10%."
    )
    months: int = Field(ge=1, le=planner.MAX_MONTHS, description="Months to reach the goal.")


class ProjectPayoffArgs(BaseModel):
    account_id: str = Field(description="ID of a credit card or loan account.")
    monthly_payment: float = Field(ge=0, description="Dollars paid every month.")
    months: int = Field(ge=1, le=planner.MAX_MONTHS)


# Floats are only used at the LLM boundary (JSON numbers). Convert via str() so
# 0.1 becomes Decimal("0.1"), not Decimal(0.1000000000000000055511151231257827).
def _dec(value: float) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args_model: type[BaseModel]
    run: Callable[[FinancialProfile, Any], BaseModel | dict[str, Any]]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_model.model_json_schema(),
            },
        }


TOOLS: tuple[Tool, ...] = (
    Tool(
        name="get_accounts",
        description="List every account the user has across all banks, with balances, "
        "rates and credit limits. Call this first to learn account IDs.",
        args_model=NoArgs,
        run=lambda profile, _: {
            "display_name": profile.display_name,
            "monthly_income": profile.monthly_income,
            "monthly_expenses": profile.monthly_expenses,
            "accounts": [a.model_dump() for a in profile.accounts],
        },
    ),
    Tool(
        name="get_health_report",
        description="Compute the user's financial health indicators (credit utilization, "
        "emergency fund, savings rate, avoidable interest) with a status for each.",
        args_model=NoArgs,
        run=lambda profile, _: indicators.health_report(profile),
    ),
    Tool(
        name="plan_credit_utilization_goal",
        description="Compute the exact monthly payment needed to bring one credit card to a "
        "target utilization within a number of months, including interest.",
        args_model=PlanUtilizationArgs,
        run=lambda profile, a: planner.plan_utilization_goal(
            profile, a.account_id, _dec(a.target_utilization_percent) / 100, a.months
        ),
    ),
    Tool(
        name="project_debt_payoff",
        description="What-if simulator: month-by-month balance of a card or loan if the user "
        "pays a fixed amount every month.",
        args_model=ProjectPayoffArgs,
        run=lambda profile, a: planner.project(
            profile, a.account_id, _dec(a.monthly_payment), a.months
        ),
    ),
)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    payload: dict[str, Any]

    def to_message_content(self) -> str:
        return json.dumps(self.payload, default=str)  # Decimal -> "123.45"


class ToolRegistry:
    def __init__(self, profile: FinancialProfile, tools: tuple[Tool, ...] = TOOLS) -> None:
        self._profile = profile
        self._tools = {t.name: t for t in tools}

    def schemas(self) -> list[dict[str, Any]]:
        return [t.schema() for t in self._tools.values()]

    def call(self, name: str, raw_arguments: str | None) -> ToolResult:
        """Run a tool. Errors go back to the model as data so it can recover, never crash."""
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(False, {"error": f"Unknown tool {name!r}"})
        try:
            args = tool.args_model.model_validate_json(raw_arguments or "{}")
        except ValidationError as exc:
            details = exc.errors(include_url=False, include_context=False, include_input=False)
            return ToolResult(False, {"error": "Invalid arguments", "details": details})
        try:
            result = tool.run(self._profile, args)
        except DomainError as exc:
            return ToolResult(False, {"error": str(exc)})
        payload = result.model_dump(mode="json") if isinstance(result, BaseModel) else result
        return ToolResult(True, json.loads(json.dumps(payload, default=str)))
