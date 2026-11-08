"""Fictional product rules and Decimal repayment calculations."""
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP, localcontext
from uuid import uuid4
from fastapi import HTTPException
from .database import utcnow
from .models import MortgageApplication
from .schemas import ApplicationIn, Installment

CENT = Decimal("0.01")
PRODUCTS = {
    "mortgage": {"name": "Mock Fixed-Rate Mortgage", "minimum": "50000", "maximum": "750000",
                 "apr": "0.0625", "terms": [180, 240, 360]},
}


def payment_for(amount: Decimal, apr: Decimal, months: int) -> Decimal:
    with localcontext() as context:
        context.prec = 40
        rate = apr / 12
        payment = amount / months if rate == 0 else amount * rate / (1 - (1 + rate) ** -months)
        return payment.quantize(CENT, rounding=ROUND_HALF_UP)


def build_application(body: ApplicationIn, customer_id: str, application_id: str | None = None,
                      created_at: datetime | None = None) -> MortgageApplication:
    product = PRODUCTS[body.mortgage_type]
    amount = body.property_value - body.down_payment
    if not Decimal(product["minimum"]) <= amount <= Decimal(product["maximum"]):
        raise HTTPException(422, "Amount is outside this product's advertised range")
    if body.term_months not in product["terms"]:
        raise HTTPException(422, "Choose a term advertised for this product")
    apr = Decimal(product["apr"])
    payment = payment_for(amount, apr, body.term_months)
    # Explicit fictional rules, not underwriting or a real lending recommendation.
    if body.down_payment / body.property_value < Decimal("0.05"):
        status, reason = "declined", "Mock minimum down payment is 5%"
    elif body.credit_score < 620:
        status, reason = "declined", "Mock credit score threshold is 620"
    elif (body.existing_monthly_debt + payment) / (body.annual_income / 12) > Decimal("0.40"):
        status, reason = "declined", "Mock monthly debt-to-income limit is 40%"
    else:
        status, reason = "approved", "Meets the fictional score and debt-to-income rules"
    return MortgageApplication(id=application_id or str(uuid4()), customer_id=customer_id,
        **body.model_dump(), amount=amount, loan_to_value=(amount/body.property_value).quantize(Decimal("0.0001")), apr=apr, monthly_payment=payment, status=status, decision_reason=reason,
        created_at=created_at or utcnow())


def schedule_for(application: MortgageApplication) -> list[Installment]:
    balance = application.amount
    origin = application.created_at.date()
    result = []
    for number in range(1, application.term_months + 1):
        month_index = origin.year * 12 + origin.month - 1 + number
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        due = date(year, month, min(origin.day, monthrange(year, month)[1]))
        interest = (balance * application.apr / 12).quantize(CENT, rounding=ROUND_HALF_UP)
        payment = min(application.monthly_payment, balance + interest)
        # Clear rounding residue in the final installment, preserving cent accuracy.
        if number == application.term_months:
            payment = balance + interest
        principal = payment - interest
        balance = (balance - principal).quantize(CENT)
        result.append(Installment(installment=number, due_date=due, payment=payment,
                                  principal=principal, interest=interest, remaining_balance=balance))
    return result


