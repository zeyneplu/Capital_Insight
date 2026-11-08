from datetime import date
from typing import Annotated
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import select, func
from ..dependencies import SessionDep, AccountDep, CustomerDep
from ..models import Transaction
from ..schemas import TransactionPage, Category, TransactionIn, PostingOut
from ..postings import post_transaction
router = APIRouter(prefix="/v1/accounts", tags=["Transactions"])


@router.get("/{account_id}/transactions", response_model=TransactionPage,
            summary="List owned transactions, newest first", description="Inclusive date filters. Amounts are nonnegative decimal strings; direction determines their balance effect.")
def transactions(session: SessionDep, account: AccountDep,
                 limit: Annotated[int, Query(ge=1, le=100)] = 50,
                 offset: Annotated[int, Query(ge=0)] = 0,
                 start_date: date | None = None, end_date: date | None = None,
                 category: Category | None = None):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be on or before end_date")
    filters = [Transaction.account_id == account.id]
    if start_date:
        filters.append(Transaction.transaction_date >= start_date)
    if end_date:
        filters.append(Transaction.transaction_date <= end_date)
    if category:
        filters.append(Transaction.category == category)
    total = session.scalar(select(func.count()).select_from(Transaction).where(*filters))
    items = session.scalars(select(Transaction).where(*filters).order_by(
        Transaction.transaction_date.desc(), Transaction.created_at.desc(), Transaction.id.desc()).offset(offset).limit(limit)).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/{account_id}/transactions", response_model=PostingOut, status_code=201,
             summary="Post an idempotent simulated transaction to an owned mock account")
def create_transaction(account_id: str, body: TransactionIn, session: SessionDep, customer: CustomerDep):
    return post_transaction(session,customer.id,account_id,body)
