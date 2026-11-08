from typing import Annotated
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Customer
from .security import token_customer

bearer = HTTPBearer(auto_error=False, description="Paste the mock access_token returned by verify-code.")


def get_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def current_customer(request: Request, session: SessionDep,
                     credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    try:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise ValueError()
        cid = token_customer(request.app.state.secret, request.app.state.settings.lender_id, credentials.credentials)
        customer = session.get(Customer, cid)
        if customer is None:
            raise ValueError()
        return customer
    except ValueError:
        raise HTTPException(401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})


CustomerDep = Annotated[Customer, Depends(current_customer)]


