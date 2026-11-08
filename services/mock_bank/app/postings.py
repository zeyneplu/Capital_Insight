"""Atomic, idempotent postings to fictional bank accounts. No money movement APIs."""
from decimal import Decimal
import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from .database import utcnow
from .models import Account, Transaction, Posting

CASH = {"checking", "savings"}
LOANS = {"personal_loan", "auto_loan", "mortgage"}
LABELS = {
    "deposit":"Deposit", "withdrawal":"Cash withdrawal", "salary":"Salary",
    "purchase":"Purchase", "payment":"Bill payment", "refund":"Refund",
    "transfer":"Transfer", "card_payment":"Credit card payment",
    "loan_payment":"Loan principal payment", "interest":"Interest", "fee":"Fee",
}


def post_transaction(session, customer_id, account_id, body):
    # Serialize across SQLite workers before reading balances or idempotency records.
    session.connection().exec_driver_sql("BEGIN IMMEDIATE")
    account = session.scalar(select(Account).where(Account.id == account_id, Account.customer_id == customer_id)
        .execution_options(populate_existing=True))
    if account is None:
        raise HTTPException(404, "Account not found")
    amount = body.amount.quantize(Decimal("0.01"))
    payload = body.model_dump(mode="json", exclude={"request_id"})
    payload.update(amount=format(amount,"f"), account_id=account.id)
    fingerprint = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    prior = session.scalar(select(Posting).where(Posting.customer_id == customer_id, Posting.request_id == body.request_id))
    if prior:
        if prior.fingerprint != fingerprint:
            raise HTTPException(409, "This request ID was already used for a different transaction")
        by_id = {transaction.id:transaction for transaction in session.scalars(select(Transaction).where(Transaction.id.in_(prior.transaction_ids)))}
        transactions = [by_id[transaction_id] for transaction_id in prior.transaction_ids]
        return {"posting_id":prior.id,"transactions":transactions,"simulated":True,"replayed":True}

    kind, operation = account.account_type, body.operation
    paired = operation in {"transfer","card_payment","loan_payment"}
    if paired != (body.counterparty_account_id is not None):
        raise HTTPException(422, "Transfers and card/loan payments require another owned account; other actions do not")
    other = None
    if paired:
        other = session.scalar(select(Account).where(Account.id == body.counterparty_account_id, Account.customer_id == customer_id))
        if other is None:
            raise HTTPException(404, "Other account not found")
        if other.id == account.id or other.currency != account.currency or other.institution_id != account.institution_id:
            raise HTTPException(422, "Choose a different account in the same institution and currency")

    # direction describes money flow; liability credits reduce the amount owed.
    category = body.category or "other"
    entries = []
    if operation in {"deposit","salary","withdrawal","payment"}:
        if kind not in CASH:
            raise HTTPException(422, "This action requires a checking or savings account")
        direction = "credit" if operation in {"deposit","salary"} else "debit"
        category = "salary" if operation == "salary" else "transfers" if operation in {"deposit","withdrawal"} else category
        entries = [(account,direction)]
    elif operation in {"purchase","refund","fee","interest"}:
        if kind not in CASH | {"credit_card"}:
            raise HTTPException(422, "This action is available only for cash accounts and credit cards")
        direction = "credit" if operation == "refund" or (operation == "interest" and kind in CASH) else "debit"
        category = "other" if operation in {"fee","interest"} else category
        entries = [(account,direction)]
    elif operation == "transfer":
        if kind not in CASH or other.account_type not in CASH:
            raise HTTPException(422, "Transfers require two checking/savings accounts")
        category = "transfers"
        entries = [(account,"debit"),(other,"credit")]
    elif operation in {"card_payment","loan_payment"}:
        if (operation == "card_payment" and kind != "credit_card") or (operation == "loan_payment" and kind not in LOANS):
            raise HTTPException(422, "Choose the appropriate card or loan account")
        if other.account_type not in CASH:
            raise HTTPException(422, "The funding account must be checking or savings")
        category = "debt_payment"
        entries = [(other,"debit"),(account,"credit")]
    if operation in {"purchase","refund","payment"} and category in {"salary","transfers","debt_payment"}:
        raise HTTPException(422, "Choose a spending category for this action")

    # Validate every leg before mutating any balance.
    balances = []
    for target, direction in entries:
        sign = 1 if direction == "credit" else -1
        if target.account_type in LOANS | {"credit_card"}:
            sign *= -1
        balance = target.balance + amount * sign
        if balance < 0:
            raise HTTPException(409, "Insufficient funds or payment/refund exceeds the amount owed")
        if balance > Decimal("999999999999.99"):
            raise HTTPException(422, "Balance would exceed the demo account limit")
        if target.credit_limit is not None and balance > target.credit_limit:
            raise HTTPException(409, "This charge would exceed the card credit limit")
        balances.append((target,balance))

    now = utcnow()
    transactions = []
    for target, direction in entries:
        transactions.append(Transaction(id="tx-"+str(uuid4()),account_id=target.id,transaction_date=now.date(),
            description=body.description or LABELS[operation],merchant=body.merchant or "Simulated transaction",
            category=category,amount=amount,direction=direction,transaction_type=operation,created_at=now))
    for target, balance in balances:
        target.balance, target.updated_at = balance, now
        if target.account_type in LOANS:
            target.outstanding_principal = balance
        if target.account_type == "credit_card":
            target.minimum_payment = min(balance,max(Decimal("25.00"),(balance*Decimal("0.02")).quantize(Decimal("0.01"))))
    posting = Posting(id=str(uuid4()),customer_id=customer_id,request_id=body.request_id,
        fingerprint=fingerprint,transaction_ids=[transaction.id for transaction in transactions])
    session.add_all([*transactions,posting])
    session.commit()
    return {"posting_id":posting.id,"transactions":transactions,"simulated":True,"replayed":False}
