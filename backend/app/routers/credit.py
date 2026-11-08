"""One synthetic current credit snapshot, authorized through connected mock banks."""
import asyncio
from datetime import date

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..database import utcnow
from ..dependencies import SessionDep, VerifiedUserDep
from ..models import Connection, CreditProfile
from ..providers import mock_call, mock_token

router = APIRouter(prefix="/v1", tags=["Credit profile"])
MODEL = "Synthetic demo score v1"


class CreditScoreOut(BaseModel):
    score: int | None = Field(default=None, ge=300, le=850)
    minimum: int = 300
    maximum: int = 850
    model: str = MODEL
    synthetic: bool = True
    as_of: date | None = None
    sources: list[str] = Field(default_factory=list)
    status: str


@router.get("/credit-score", response_model=CreditScoreOut,
            summary="Get one current synthetic credit score from consenting mock banks")
async def credit_score(request: Request, session: SessionDep, user: VerifiedUserDep):
    links = session.scalars(select(Connection).where(Connection.user_id == user.id,
        Connection.kind == "mock_bank")).all()
    links = [link for link in links if link.expires_at is None or link.expires_at > utcnow()]
    if not links:
        return {"status":"connect_bank"}

    async def fetch(link):
        try:
            profile = await mock_call(request, link.provider, "/v1/customers/me", token=mock_token(request, link))
            score = profile.get("credit_score")
            as_of = date.fromisoformat(profile["credit_score_as_of"])
            if type(score) is not int or not 300 <= score <= 850:
                return None
            return link, profile, score, as_of
        except (HTTPException, KeyError, TypeError, ValueError):
            # An unavailable bank must not fabricate a score or expose provider details.
            return None

    reports = [report for report in await asyncio.gather(*(fetch(link) for link in links)) if report]
    if not reports:
        return {"status":"unavailable"}
    # Different mock customer identities may have been linked to this app account.
    # Never average their scores or silently choose a conflicting report.
    if len({report[2] for report in reports}) != 1:
        return {"status":"conflicting_profiles"}
    score = reports[0][2]
    as_of = max(report[3] for report in reports)
    profile = session.get(CreditProfile, user.id)
    if profile is None:
        profile = CreditProfile(user_id=user.id, score=score, model=MODEL, as_of=as_of)
        session.add(profile)
    else:
        profile.score, profile.model, profile.as_of = score, MODEL, as_of
    for link, customer, _, _ in reports:
        link.customer_profile = customer
    try:
        session.commit()
    except IntegrityError:
        # Two dashboard loads may discover the same profile concurrently.
        session.rollback()
        profile = session.get(CreditProfile, user.id)
        if profile is None:
            raise
        profile.score, profile.model, profile.as_of = score, MODEL, as_of
        session.commit()
    return {"score":profile.score, "as_of":profile.as_of,
        "sources":sorted({report[0].display_name for report in reports}), "status":"available"}
