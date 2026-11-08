from fastapi import APIRouter, Request
from sqlalchemy import text
from ..dependencies import SessionDep
from ..loan_service import PRODUCTS
from ..schemas import HealthOut, LenderOut

router = APIRouter(tags=["Lender"])


@router.get("/health", response_model=HealthOut, summary="Check service and database health")
def health(request: Request, session: SessionDep):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "lender_id": request.app.state.settings.lender_id}


@router.get("/v1/lender", response_model=LenderOut, summary="Get this fictional lender's metadata")
def lender(request: Request):
    settings = request.app.state.settings
    return {"id": settings.lender_id, "name": settings.lender_name, "loan_types": list(PRODUCTS)}
