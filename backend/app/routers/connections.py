from datetime import timedelta
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from ..database import utcnow
from ..dependencies import SessionDep, UserDep, ConnectionDep
from ..models import Connection, CachedTransaction, PlaidState
from ..providers import PROVIDERS, mock_call, mock_token, segment
from ..schemas import ConnectionOut, CodeRequest, VerifyRequest, ProviderOut, Message

router = APIRouter(prefix="/v1", tags=["Connections"])


@router.get("/providers", response_model=list[ProviderOut], summary="List available institution adapters")
def providers(request: Request):
    settings = request.app.state.settings
    return [{"id": key, "name": name, "kind": kind, "configured": key in settings.mock_service_urls}
            for key, (name, kind) in PROVIDERS.items()] + [{"id": "plaid", "name": "Plaid", "kind": "plaid",
                "configured": bool(settings.plaid_client_id and settings.plaid_secret)}]


@router.get("/connections", response_model=list[ConnectionOut], summary="List your linked institutions")
def connections(session: SessionDep, user: UserDep):
    return session.scalars(select(Connection).where(Connection.user_id == user.id).order_by(Connection.created_at)).all()


@router.post("/connections/{provider}/request-code", response_model=Message, status_code=202,
             summary="Ask a mock institution to issue a consent code")
async def request_code(provider: str, body: CodeRequest, request: Request, user: UserDep):
    return await mock_call(request, provider, "/v1/auth/request-code", method="POST", body=body.model_dump())


@router.post("/connections/{provider}/verify-code", response_model=ConnectionOut,
             summary="Verify mock consent and save encrypted institution credentials")
async def verify_code(provider: str, body: VerifyRequest, request: Request, session: SessionDep, user: UserDep):
    token = await mock_call(request, provider, "/v1/auth/verify-code", method="POST", body=body.model_dump())
    customer = await mock_call(request, provider, "/v1/customers/me", token=token["access_token"])
    connection = session.scalar(select(Connection).where(Connection.user_id == user.id,
                                Connection.provider == provider, Connection.remote_id == customer["id"]))
    if connection is None:
        connection = Connection(user_id=user.id, provider=provider, kind=PROVIDERS[provider][1],
            remote_id=customer["id"], display_name=PROVIDERS[provider][0])
        session.add(connection)
    connection.encrypted_token = request.app.state.cipher.encrypt(token["access_token"].encode()).decode()
    connection.expires_at = utcnow()+timedelta(seconds=int(token["expires_in"]))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "Connection was updated concurrently; retry authorization")
    return connection


@router.delete("/connections/{connection_id}", status_code=204, summary="Disconnect an institution and remove cached transactions")
async def disconnect(request: Request, session: SessionDep, connection: ConnectionDep):
    if connection.kind == "plaid":
        from ..plaid import PlaidClient, access_token_for
        access_token = access_token_for(request, connection)
        await PlaidClient(request.app.state.settings, request.app.state.http_client).call("/item/remove", {"access_token": access_token})
    session.execute(delete(CachedTransaction).where(CachedTransaction.connection_id == connection.id))
    session.execute(delete(PlaidState).where(PlaidState.connection_id == connection.id))
    session.delete(connection)
    session.commit()


@router.get("/connections/{connection_id}/offers", summary="Get a linked loan or mortgage provider's current mock offers")
async def offers(request: Request, connection: ConnectionDep):
    if connection.kind not in {"mock_loan", "mock_mortgage"}:
        raise HTTPException(404, "This connection does not offer loan applications")
    path = "/v1/loan-offers" if connection.kind == "mock_loan" else "/v1/mortgage-offers"
    return await mock_call(request, connection.provider, path)


def application_path(connection):
    if connection.kind not in {"mock_loan", "mock_mortgage"}:
        raise HTTPException(404, "Loan or mortgage connection required")
    return "/v1/loan-applications" if connection.kind == "mock_loan" else "/v1/mortgage-applications"


@router.get("/connections/{connection_id}/applications", summary="List your applications at a linked mock lender")
async def applications(request: Request, connection: ConnectionDep):
    return await mock_call(request, connection.provider, application_path(connection), token=mock_token(request, connection))


@router.post("/connections/{connection_id}/applications", status_code=201,
             summary="Submit a simulated loan or mortgage application",
             description="Request fields follow the selected service's /v1/loan-applications or /v1/mortgage-applications schema. A declined decision still returns 201.")
async def apply(body: dict, request: Request, connection: ConnectionDep):
    return await mock_call(request, connection.provider, application_path(connection), method="POST",
                           token=mock_token(request, connection), body=body)


@router.get("/connections/{connection_id}/records/{record_id}/schedule", summary="Get your simulated repayment schedule")
async def schedule(record_id: str, request: Request, connection: ConnectionDep):
    application_path(connection)
    prefix = "/v1/loans" if connection.kind == "mock_loan" else "/v1/mortgages"
    return await mock_call(request, connection.provider, f"{prefix}/{segment(record_id)}/schedule", token=mock_token(request, connection))
