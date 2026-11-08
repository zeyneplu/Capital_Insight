from fastapi import APIRouter, Request
from sqlalchemy import text
from ..dependencies import SessionDep
from ..schemas import HealthOut, InstitutionOut
from ..seed import PRODUCTS

router = APIRouter(tags=["Institution"])


@router.get("/health", response_model=HealthOut, summary="Check service and database health")
def health(request: Request, session: SessionDep):
    session.execute(text("SELECT 1"))
    return {"status": "ok", "bank_id": request.app.state.settings.bank_id}


@router.get("/v1/institution", response_model=InstitutionOut, summary="Get this simulated bank's metadata")
def institution(request: Request):
    settings = request.app.state.settings
    return {"id": settings.bank_id, "name": settings.bank_name,
            "products": PRODUCTS.get(settings.bank_id, ["checking", "savings"])}
