from typing import Annotated
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Customer, Account
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
        cid = token_customer(request.app.state.secret, request.app.state.settings.bank_id, credentials.credentials)
        customer = session.get(Customer, cid)
        if customer is None:
            raise ValueError()
        return customer
    except ValueError:
        raise HTTPException(401, "Invalid or expired access token", headers={"WWW-Authenticate": "Bearer"})


CustomerDep = Annotated[Customer, Depends(current_customer)]


def owned_account(account_id: str, session: SessionDep, customer: CustomerDep):
    account = session.scalar(select(Account).where(Account.id == account_id, Account.customer_id == customer.id))
    if account is None:
        # Use the same response for absent accounts and accounts belonging to others.
        raise HTTPException(404, "Account not found")
    return account


AccountDep = Annotated[Account, Depends(owned_account)]
