"""Emit golden values from the real service code. Usage: golden.py <loan|mortgage>"""
import json, sys
from datetime import datetime, timezone
from fastapi import HTTPException
kind = sys.argv[1]
if kind == "loan":
    from app.loan_service import payment_for, build_application, schedule_for
    from app.schemas import ApplicationIn
    cases = [
        dict(loan_type="personal_loan", amount="10000.00", term_months=36, annual_income="90000.00", existing_monthly_debt="300.00", credit_score=690),
        dict(loan_type="auto_loan", amount="25000.00", term_months=60, annual_income="90000.00", existing_monthly_debt="300.00", credit_score=690),
        dict(loan_type="auto_loan", amount="40000.00", term_months=72, annual_income="60000.00", existing_monthly_debt="400.00", credit_score=600),
        dict(loan_type="personal_loan", amount="50000.00", term_months=12, annual_income="40000.00", existing_monthly_debt="0.00", credit_score=800),
        dict(loan_type="mortgage", amount="333333.33", term_months=360, annual_income="200000.00", existing_monthly_debt="1000.00", credit_score=760),
        dict(loan_type="personal_loan", amount="999.00", term_months=36, annual_income="90000.00", existing_monthly_debt="0", credit_score=700),
        dict(loan_type="personal_loan", amount="5000.00", term_months=30, annual_income="90000.00", existing_monthly_debt="0", credit_score=700),
    ]
else:
    from app.mortgage_service import payment_for, build_application, schedule_for
    from app.schemas import ApplicationIn
    cases = [
        dict(property_value="350000.00", down_payment="70000.00", term_months=360, annual_income="120000.00", existing_monthly_debt="500.00", credit_score=740),
        dict(property_value="275000.00", down_payment="55000.00", term_months=180, annual_income="150000.00", existing_monthly_debt="300.00", credit_score=690),
        dict(property_value="400000.00", down_payment="10000.00", term_months=360, annual_income="150000.00", existing_monthly_debt="300.00", credit_score=760),
        dict(property_value="500000.00", down_payment="100000.00", term_months=240, annual_income="60000.00", existing_monthly_debt="300.00", credit_score=760),
        dict(property_value="333333.00", down_payment="33333.33", term_months=240, annual_income="250000.00", existing_monthly_debt="0", credit_score=700),
        dict(property_value="1000000.00", down_payment="200000.00", term_months=360, annual_income="900000.00", existing_monthly_debt="0", credit_score=800),
    ]
created = datetime(2024, 1, 31, 15, 0, tzinfo=timezone.utc)
out = []
for c in cases:
    body = ApplicationIn(**c)
    try:
        app = build_application(body, "c1", "a1", created)
    except HTTPException as e:
        out.append({"input": c, "error": {"status": e.status_code, "detail": e.detail}}); continue
    rec = {"input": c, "status": app.status, "decision_reason": app.decision_reason,
           "apr": str(app.apr), "monthly_payment": str(app.monthly_payment)}
    if kind == "mortgage":
        rec["amount"] = str(app.amount); rec["loan_to_value"] = str(app.loan_to_value)
    sched = schedule_for(app)
    pick = lambda r: {"installment": r.installment, "due_date": r.due_date.isoformat(), "payment": str(r.payment),
                      "principal": str(r.principal), "interest": str(r.interest), "remaining_balance": str(r.remaining_balance)}
    rec["schedule_len"] = len(sched)
    rec["schedule_sample"] = [pick(r) for r in sched[:3]] + [pick(r) for r in sched[-2:]]
    rec["total_interest"] = str(sum(r.interest for r in sched))
    out.append(rec)
print(json.dumps(out, indent=1))
