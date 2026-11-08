from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from ..dependencies import CustomerDep, SessionDep
from ..models import LoanApplication
from ..schemas import Offer, ApplicationIn, ApplicationOut, Installment
from ..loan_service import PRODUCTS, build_application, schedule_for

router = APIRouter(prefix="/v1", tags=["Mock loans"])


@router.get("/loan-offers", response_model=list[Offer], summary="Browse fictional loan products (public)")
def offers():
    return [Offer(loan_type=kind, name=p["name"], minimum_amount=p["minimum"],
                  maximum_amount=p["maximum"], apr=p["apr"], terms_months=p["terms"]) for kind, p in PRODUCTS.items()]


@router.post("/loan-applications", response_model=ApplicationOut, status_code=201,
             summary="Submit a fictional application and receive a simulated decision",
             description="Uses self-reported mock income, debt and credit score. Approval does not disburse money.")
def apply(body: ApplicationIn, session: SessionDep, customer: CustomerDep):
    application = build_application(body, customer.id)
    session.add(application)
    session.commit()
    return application


@router.get("/loan-applications", response_model=list[ApplicationOut], summary="List your fictional applications")
def applications(session: SessionDep, customer: CustomerDep):
    return session.scalars(select(LoanApplication).where(LoanApplication.customer_id == customer.id)
                           .order_by(LoanApplication.created_at.desc(), LoanApplication.id)).all()


def owned_application(session, customer, application_id):
    application = session.scalar(select(LoanApplication).where(LoanApplication.id == application_id,
                                                              LoanApplication.customer_id == customer.id))
    if application is None:
        raise HTTPException(404, "Loan application not found")
    return application


@router.get("/loan-applications/{application_id}", response_model=ApplicationOut, summary="Read your application decision")
def application(application_id: str, session: SessionDep, customer: CustomerDep):
    return owned_application(session, customer, application_id)


@router.get("/loans", response_model=list[ApplicationOut], summary="List your approved simulated loans")
def loans(session: SessionDep, customer: CustomerDep):
    return session.scalars(select(LoanApplication).where(LoanApplication.customer_id == customer.id,
                           LoanApplication.status == "approved").order_by(LoanApplication.id)).all()


@router.get("/loans/{loan_id}/schedule", response_model=list[Installment], summary="Preview a simulated repayment schedule")
def schedule(loan_id: str, session: SessionDep, customer: CustomerDep):
    application = owned_application(session, customer, loan_id)
    if application.status != "approved":
        raise HTTPException(409, "Only approved simulated loans have repayment schedules")
    return schedule_for(application)


@router.get("/loans/{loan_id}", response_model=ApplicationOut, summary="Read your approved simulated loan")
def loan(loan_id: str, session: SessionDep, customer: CustomerDep):
    application = owned_application(session, customer, loan_id)
    if application.status != "approved":
        raise HTTPException(404, "Approved simulated loan not found")
    return application
