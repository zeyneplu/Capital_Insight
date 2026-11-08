"""Deterministic USD scenarios. Models explain these results; they never supply the math."""
from decimal import Decimal, ROUND_HALF_UP, localcontext

D = Decimal
CENT = D("0.01")


def money(value):
    return format(D(str(value)).quantize(CENT, rounding=ROUND_HALF_UP),"f")


def goal_projection(parameters):
    initial, monthly, target = (D(str(parameters.get(key,"0"))) for key in ("saved_amount","monthly_contribution","target_amount"))
    months = int(parameters["months"])
    annual = D(str(parameters.get("annual_return_pct","0")))
    with localcontext() as context:
        context.prec = 40
        rate = annual / 1200
        growth = (1+rate)**months
        factor = (growth-1)/rate if rate else D(months)
        needed = max(D(0),(target-initial*growth)/factor)
        projected = initial*growth+monthly*factor
        points = []
        for month in sorted(set([0,months,*range(0,months+1,max(1,months//24))])):
            g = (1+rate)**month
            value = initial*g+monthly*((g-1)/rate if rate else D(month))
            points.append({"month":month,"amount":money(value)})
    return {"projected_amount":money(projected),"required_monthly":money(needed),
        "shortfall":money(max(D(0),target-projected)),"on_track":projected>=target,
        "progress_pct":float(min(D(100),initial/target*100)) if target else 0,
        "points":points,"assumptions":["USD, month-end contributions, constant assumed return", "Excludes taxes, fees and inflation; investment returns are not guaranteed"]}


def credit_payment_plan(cards, months, utilization_pct):
    rows = []
    for card in cards:
        if card.get("credit_limit") is None or D(str(card["credit_limit"]))<=0:
            continue
        balance, limit = D(str(card["balance"])), D(str(card["credit_limit"]))
        target = min(balance, limit*D(str(utilization_pct))/100)
        apr = card.get("apr")
        rate = D(str(apr or "0"))/12
        with localcontext() as context:
            context.prec = 40
            growth = (1+rate)**months
            payment = max(D(0),(balance*growth-target)*rate/(growth-1)) if rate else (balance-target)/months
        minimum = D(str(card.get("minimum_payment") or "0"))
        payment = max(payment,minimum)
        rows.append({"account_ref":card["ref"],"balance":money(balance),"credit_limit":money(limit),
            "utilization_pct":round(float(balance/limit*100),1),"target_balance":money(target),
            "monthly_payment":money(payment),"apr":apr,"apr_unknown":apr is None})
    return {"cards":rows,"monthly_payment":money(sum(D(row["monthly_payment"]) for row in rows)),
        "target_utilization_pct":str(utilization_pct),"months":months,
        "assumptions":["No new charges or fees; constant APR and credit limits", "Unknown APR is modeled at 0% only as a lower-bound estimate", "Utilization targets do not predict or guarantee a credit score or timeline"]}
