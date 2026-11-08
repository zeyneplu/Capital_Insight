"""Owned financial aggregates and possible recurring charges; no secrets in model context."""
import asyncio
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from statistics import median

from fastapi import HTTPException
from sqlalchemy import select

from .database import utcnow
from .models import Connection, CachedTransaction, CreditProfile
from .providers import mock_call, mock_token, segment
from .routers.portfolio import collect
from .planning_math import money

D = Decimal
EXCLUDED = {"transfers","transfer_in","transfer_out","debt_payment","loan_payments"}


def recurring_charges(transactions):
    groups = defaultdict(list)
    for row in transactions:
        merchant = str(row.get("merchant") or "").strip()[:80]
        category = str(row.get("category") or "other").lower()
        if row.get("direction")!="debit" or not merchant or category in EXCLUDED | {"groceries","rent","salary","income","medical","healthcare"}:
            continue
        groups[merchant.casefold()].append(row)
    result=[]
    for rows in groups.values():
        by_date = {row["transaction_date"]:row for row in rows}
        ordered = sorted(by_date.values(),key=lambda row:row["transaction_date"])
        if len(ordered)<3:
            continue
        dates=[date.fromisoformat(row["transaction_date"]) for row in ordered]
        gaps=[(b-a).days for a,b in zip(dates,dates[1:])]
        typical=median(gaps)
        cadence="monthly" if 25<=typical<=35 else "weekly" if 6<=typical<=8 else None
        amounts=[D(str(row["amount"])) for row in ordered]
        typical_amount=D(str(median(amounts)))
        if not cadence or typical_amount<=0 or max(amounts)-min(amounts)>typical_amount*D("0.1"):
            continue
        if sum((25<=gap<=35) if cadence=="monthly" else (6<=gap<=8) for gap in gaps)<len(gaps)*0.8:
            continue
        result.append({"merchant":str(ordered[0]["merchant"])[:80],"amount":money(typical_amount),
            "monthly_estimate":money(typical_amount*(D("52")/12 if cadence=="weekly" else 1)),
            "cadence":cadence,"occurrences":len(ordered),"status":"possible_recurring_charge"})
    return sorted(result,key=lambda row:D(row["monthly_estimate"]),reverse=True)[:12]


def summarize(accounts, transactions, preferences, errors=None):
    today=utcnow().date()
    start=today-timedelta(days=89)
    usable=[]
    for row in transactions:
        try:
            day=date.fromisoformat(str(row["transaction_date"])[:10])
            amount=D(str(row["amount"]))
            if start<=day<=today and amount.is_finite() and amount>=0 and not row.get("pending",False):
                usable.append({**row,"transaction_date":day.isoformat(),"amount":money(amount)})
        except (ValueError,TypeError,KeyError,InvalidOperation):
            continue
    oldest=min((date.fromisoformat(row["transaction_date"]) for row in usable),default=today)
    days=min(90,(today-oldest).days+1) if usable else 0
    income=spending=D(0)
    categories=defaultdict(lambda:D(0))
    recent=previous=D(0)
    for row in usable:
        amount=D(row["amount"])
        category=str(row.get("category") or "other").lower()
        if row.get("direction")=="credit" and category in {"salary","income"}:
            income+=amount
        elif row.get("direction")=="debit" and category not in EXCLUDED:
            spending+=amount
            categories[category]+=amount
            age=(today-date.fromisoformat(row["transaction_date"])).days
            if age<30: recent+=amount
            elif age<60: previous+=amount
    observed_income=money(income*30/days) if days>=30 else None
    monthly_income=preferences.get("monthly_income") if preferences.get("monthly_income") is not None else observed_income
    monthly_spending=money(spending*30/days) if days>=30 else None
    liquid=sum((D(row["balance"]) for row in accounts if row["type"] in {"checking","savings","money_market","cash_management"}),D(0))
    debt=sum((max(D(0),D(row["balance"])) for row in accounts if row["balance_kind"]=="liability"),D(0))
    cards=[row for row in accounts if row["type"]=="credit_card" or row.get("source_type")=="credit"]
    known_cards=[row for row in cards if row.get("credit_limit") is not None and D(row["credit_limit"])>0]
    limits=sum((D(row["credit_limit"]) for row in known_cards),D(0))
    card_balances=sum((max(D(0),D(row["balance"])) for row in known_cards),D(0))
    minimums=sum((D(row.get("minimum_payment") or "0") for row in accounts if row["balance_kind"]=="liability"),D(0))
    free=money(D(str(monthly_income))-D(monthly_spending)-minimums) if monthly_income is not None and monthly_spending is not None else None
    alerts=[]
    budget=preferences.get("monthly_budget")
    if budget is not None and recent>D(str(budget)):
        alerts.append({"kind":"budget","title":"Spending is above your chosen budget","amount":money(recent-D(str(budget))),"detail":"Observed spending in the latest 30 days versus your saved monthly budget."})
    if days>=60 and previous>0 and recent>previous*D("1.2"):
        alerts.append({"kind":"spending_change","title":"Spending increased over the previous period","amount":money(recent-previous),"detail":"Latest 30 days compared with the preceding 30; review one-off purchases before changing your budget."})
    if free is not None and D(free)<0:
        alerts.append({"kind":"cashflow","title":"Estimated monthly outflow exceeds income","amount":money(-D(free)),"detail":"Uses observed income or your override, estimated spending, and known debt payments."})
    warnings=list(errors or [])
    if days<30: warnings.append("Fewer than 30 days of transaction coverage; monthly cash-flow estimates are unavailable.")
    if any(row["balance_kind"]=="liability" and row.get("minimum_payment") is None for row in accounts):
        warnings.append("Some debt minimum payments are unavailable; affordability estimates may overstate available cash.")
    return {"as_of":today.isoformat(),"currency":"USD","accounts":accounts,"cards":cards,
        "totals":{"liquid_cash":money(liquid),"debt":money(debt),"credit_limit":money(limits),
            "card_balance":money(card_balances),"utilization_pct":round(float(card_balances/limits*100),1) if limits else None},
        "cash_flow":{"coverage_days":days,"monthly_income":str(monthly_income) if monthly_income is not None else None,
            "monthly_spending":monthly_spending,"known_debt_payments":money(minimums),"monthly_free_cash":free,
            "income_source":"user_override" if preferences.get("monthly_income") is not None else "observed_estimate",
            "recent_spending":money(recent)},
        "categories":[{"category":key,"amount":money(amount)} for key,amount in sorted(categories.items(),key=lambda item:item[1],reverse=True)],
        "subscriptions":recurring_charges(usable),"alerts":alerts,"warnings":warnings}


async def build_snapshot(request,session,user,preferences):
    links=session.scalars(select(Connection).where(Connection.user_id==user.id,Connection.kind.in_(["mock_bank","plaid"]))).all()
    valid=[link for link in links if link.expires_at is None or link.expires_at>utcnow()]
    result=await collect(request,valid,"accounts")
    accounts=[]
    warnings=["A linked provider is unavailable; analysis covers the data returned." for _ in result["errors"]]
    if len(valid)<len(links): warnings.append("Some institution consents expired. Reconnect to include those accounts.")
    raw_by_ref={}
    for raw in result["items"][:80]:
        if raw.get("currency")!="USD" or raw.get("balance") is None or raw.get("balance_kind")=="unknown":
            warnings.append("A non-USD account or unknown balance is excluded from the USD scenario.")
            continue
        ref=f"A{len(accounts)+1}"
        entry={"ref":ref,"institution":raw["provider"],"type":raw["account_type"],"source_type":raw.get("source_account_type"),
            "balance":str(raw["balance"]),"balance_kind":raw["balance_kind"],
            "credit_limit":str(raw["credit_limit"]) if raw.get("credit_limit") is not None else None,
            "apr":str(raw.get("purchase_apr") or raw.get("apr")) if raw.get("purchase_apr") is not None or raw.get("apr") is not None else None,
            "minimum_payment":str(raw.get("minimum_payment") or raw.get("monthly_payment")) if raw.get("minimum_payment") is not None or raw.get("monthly_payment") is not None else None}
        accounts.append(entry); raw_by_ref[raw["id"]]=raw
    cutoff=(utcnow().date()-timedelta(days=89)).isoformat()
    rows=[]
    # Read only this user's cached Plaid history; never another user's rows.
    plaid_ids=[link.id for link in valid if link.kind=="plaid"]
    if plaid_ids:
        for row in session.scalars(select(CachedTransaction).where(CachedTransaction.connection_id.in_(plaid_ids))):
            if row.payload.get("account_id") in raw_by_ref and row.payload.get("currency")=="USD":
                rows.append(row.payload)
    semaphore=asyncio.Semaphore(8)
    by_id={link.id:link for link in valid}
    async def history(raw):
        link=by_id[raw["connection_id"]]
        if link.kind!="mock_bank": return []
        output=[]
        try:
            async with semaphore:
                for offset in range(0,600,100):
                    page=await mock_call(request,link.provider,f"/v1/accounts/{segment(raw['source_account_id'])}/transactions",
                        token=mock_token(request,link),params={"limit":100,"offset":offset,"start_date":cutoff})
                    output.extend(page["items"])
                    if offset+len(page["items"])>=page["total"]: break
                if page["total"]>600: warnings.append("Transaction analysis is capped at 600 recent rows per account.")
            return output
        except (HTTPException,KeyError,TypeError):
            warnings.append("Some transaction history could not be loaded."); return []
    rows.extend(row for batch in await asyncio.gather(*(history(raw) for raw in raw_by_ref.values())) for row in batch)
    snapshot=summarize(accounts,rows,preferences,list(dict.fromkeys(warnings)))
    profile=session.get(CreditProfile,user.id)
    snapshot["credit_score"]={"score":profile.score,"synthetic":True,"model":profile.model} if profile and any(link.kind=="mock_bank" for link in valid) else None
    return snapshot


def model_context(snapshot,goals,preferences):
    """Allowlist only aggregates; exclude bank IDs, emails, raw merchants and goal free text."""
    return {"as_of":snapshot["as_of"],"currency":"USD","accounts":snapshot["accounts"],
        "totals":snapshot["totals"],"cash_flow":snapshot["cash_flow"],"credit_score":snapshot["credit_score"],
        "categories":snapshot["categories"],
        "recurring_charges":[{key:value for key,value in row.items() if key!="merchant"} for row in snapshot["subscriptions"]],
        "alerts":snapshot["alerts"],"warnings":snapshot["warnings"],
        "goals":[{"kind":goal.kind,**{key:value for key,value in goal.parameters.items() if key!="name"}} for goal in goals],
        "investment_scenario":{key:preferences[key] for key in ("stocks_pct","bonds_pct","cash_pct")}}
