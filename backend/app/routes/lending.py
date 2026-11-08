"""Loan and mortgage lenders: offers, applications and schedules."""
from typing import Annotated

from fastapi import APIRouter, Body, Path

from ..deps import ClientDep, RegistryDep, SessionDep, authed_call, institution_or_404
from ..institutions import LENDER_PATHS
from ..upstream import UpstreamError, as_http, call

router = APIRouter(prefix="/api/v1/lenders", tags=["Lending"])
SafeId = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{1,128}$")]


async def lender_call(session, http, lender, method, path, **kwargs):
    try:
        return await authed_call(http, session, lender, method, path, **kwargs)
    except UpstreamError as error:
        raise as_http(error) from error


@router.get("/{lender_id}/offers", summary="Public product list")
async def offers(lender_id: str, http: ClientDep, registry: RegistryDep) -> list[dict]:
    lender = institution_or_404(registry, lender_id, "mock_loan", "mock_mortgage")
    try:
        return await call(http, lender, "GET", f"/v1/{LENDER_PATHS[lender.service]['offers']}")
    except UpstreamError as error:
        raise as_http(error) from error


@router.get("/{lender_id}/applications", summary="All applications (approved and declined), or connected=false")
async def applications(lender_id: str, session: SessionDep, http: ClientDep, registry: RegistryDep) -> dict:
    lender = institution_or_404(registry, lender_id, "mock_loan", "mock_mortgage")
    if session.active(lender.id) is None:
        return {"connected": False, "items": []}
    items = await lender_call(session, http, lender, "GET", f"/v1/{LENDER_PATHS[lender.service]['applications']}")
    return {"connected": True, "items": items}


@router.post("/{lender_id}/applications", status_code=201, summary="Submit an application (the service decides)")
async def apply(lender_id: str, session: SessionDep, http: ClientDep, registry: RegistryDep,
                body: Annotated[dict, Body(max_length=12)]) -> dict:
    lender = institution_or_404(registry, lender_id, "mock_loan", "mock_mortgage")
    # The lender's own schema is the authority on fields and ranges; its 422 passes through.
    return await lender_call(session, http, lender, "POST", f"/v1/{LENDER_PATHS[lender.service]['applications']}", json=body)


@router.get("/{lender_id}/applications/{application_id}/schedule", summary="Application plus its schedule, if approved")
async def schedule(lender_id: str, application_id: SafeId, session: SessionDep, http: ClientDep, registry: RegistryDep) -> dict:
    lender = institution_or_404(registry, lender_id, "mock_loan", "mock_mortgage")
    if session.active(lender.id) is None:
        return {"connected": False}
    paths = LENDER_PATHS[lender.service]
    try:
        application = await authed_call(http, session, lender, "GET", f"/v1/{paths['applications']}/{application_id}")
    except UpstreamError as error:
        if error.status == 404:
            return {"connected": True, "kind": "not_found"}
        raise as_http(error) from error
    if application["status"] != "approved":
        return {"connected": True, "kind": "declined", "application": application}
    rows = await lender_call(session, http, lender, "GET", f"/v1/{paths['records']}/{application_id}/schedule")
    return {"connected": True, "kind": "schedule", "application": application, "rows": rows}
