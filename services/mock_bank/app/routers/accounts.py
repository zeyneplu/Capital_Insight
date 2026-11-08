from fastapi import APIRouter
from sqlalchemy import select
from ..dependencies import SessionDep, CustomerDep, AccountDep
from ..models import Account
from ..schemas import AccountOut, BalanceOut, AccountType
router = APIRouter(prefix="/v1/accounts", tags=["Accounts"])


@router.get("", response_model=list[AccountOut], summary="List only the authorized customer's accounts")
def accounts(session: SessionDep, customer: CustomerDep, account_type: AccountType | None = None):
    query = select(Account).where(Account.customer_id == customer.id)
    if account_type:
        query = query.where(Account.account_type == account_type)
    return session.scalars(query.order_by(Account.id)).all()


@router.get("/{account_id}", response_model=AccountOut, summary="Read an owned account")
def account(account: AccountDep):
    return account


@router.get("/{account_id}/balance", response_model=BalanceOut, summary="Read an owned account's balance snapshot")
def balance(account: AccountDep):
    return account
