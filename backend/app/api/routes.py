"""HTTP layer: validate input, call the engine, return models. No business logic here.

Note for later: customer_id in the URL is fine for a demo with synthetic data.
In a real app the customer comes from the authenticated session, never the URL,
otherwise anyone could read anyone's data by changing the ID.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import AfterValidator, BaseModel, Field

from app.agent.coach import CoachAnswer, run_coach
from app.domain.models import FinancialProfile
from app.domain.validators import reject_ssn
from app.engine import cashflow, indicators, planner
from app.sources.base import FinancialDataSource

router = APIRouter(prefix="/api/v1")


# --- dependencies (overridable in tests) -----------------------------------


def get_source(request: Request) -> FinancialDataSource:
    return request.app.state.source


async def get_profile(
    customer_id: str, source: Annotated[FinancialDataSource, Depends(get_source)]
) -> FinancialProfile:
    return await source.get_profile(customer_id)


Profile = Annotated[FinancialProfile, Depends(get_profile)]


# --- request bodies ---------------------------------------------------------


class UtilizationGoalRequest(BaseModel):
    account_id: str
    target_utilization: Decimal = Field(ge=0, lt=1, examples=["0.10"])
    months: int = Field(ge=1, le=planner.MAX_MONTHS, examples=[6])


class ProjectionRequest(BaseModel):
    account_id: str
    monthly_payment: Decimal = Field(ge=0, examples=["75.00"])
    months: int = Field(ge=1, le=planner.MAX_MONTHS, examples=[12])


class CoachRequest(BaseModel):
    # Text validation: length limits + no SSNs, checked before anything reaches the LLM.
    question: Annotated[str, Field(min_length=1, max_length=1000), AfterValidator(reject_ssn)]


# --- routes -----------------------------------------------------------------


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/customers/{customer_id}/profile")
async def read_profile(profile: Profile) -> FinancialProfile:
    return profile


@router.get("/customers/{customer_id}/health-report")
async def read_health_report(profile: Profile) -> indicators.HealthReport:
    return indicators.health_report(profile)


@router.get("/customers/{customer_id}/cash-flow")
async def read_cash_flow(
    customer_id: str,
    source: Annotated[FinancialDataSource, Depends(get_source)],
    months: Annotated[int, Query(ge=1, le=12)] = 3,
) -> cashflow.CashFlowSummary:
    """Average monthly income, spending, and spending by category."""
    return cashflow.summarize(await source.get_transactions(customer_id), months=months)


@router.post("/customers/{customer_id}/plans/credit-utilization")
async def create_utilization_plan(
    body: UtilizationGoalRequest, profile: Profile
) -> planner.UtilizationPlan:
    return planner.plan_utilization_goal(
        profile, body.account_id, body.target_utilization, body.months
    )


@router.post("/customers/{customer_id}/projections")
async def create_projection(body: ProjectionRequest, profile: Profile) -> planner.Projection:
    return planner.project(profile, body.account_id, body.monthly_payment, body.months)


@router.post("/customers/{customer_id}/coach")
async def ask_coach(body: CoachRequest, profile: Profile, request: Request) -> CoachAnswer:
    llm = request.app.state.llm
    if llm is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI coach is not configured. Set NVIDIA_API_KEY in backend/.env.",
        )
    return await run_coach(llm, request.app.state.settings.nemotron_model, profile, body.question)
