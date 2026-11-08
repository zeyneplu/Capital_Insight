from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from ..dependencies import CustomerDep, SessionDep
from ..models import MortgageApplication
from ..schemas import Offer, ApplicationIn, ApplicationOut, Installment
from ..mortgage_service import PRODUCTS, build_application, schedule_for

router = APIRouter(prefix="/v1", tags=["Mock mortgages"])


@router.get("/mortgage-offers", response_model=list[Offer], summary="Browse fictional mortgage products (public)")
def offers():
    return [Offer(mortgage_type=kind, name=p["name"], minimum_amount=p["minimum"],
                  maximum_amount=p["maximum"], apr=p["apr"], terms_months=p["terms"]) for kind, p in PRODUCTS.items()]


@router.post("/mortgage-applications", response_model=ApplicationOut, status_code=201,
             summary="Submit a fictional application and receive a simulated decision",
             description="Uses self-reported mock income, debt and credit score. Approval does not disburse money.")
def apply(body: ApplicationIn, session: SessionDep, customer: CustomerDep):
    application = build_application(body, customer.id)
    session.add(application)
    session.commit()
    return application


@router.get("/mortgage-applications", response_model=list[ApplicationOut], summary="List your fictional applications")
def applications(session: SessionDep, customer: CustomerDep):
    return session.scalars(select(MortgageApplication).where(MortgageApplication.customer_id == customer.id)
                           .order_by(MortgageApplication.created_at.desc(), MortgageApplication.id)).all()


def owned_application(session, customer, application_id):
    application = session.scalar(select(MortgageApplication).where(MortgageApplication.id == application_id,
                                                              MortgageApplication.customer_id == customer.id))
    if application is None:
        raise HTTPException(404, "Mortgage application not found")
    return application


@router.get("/mortgage-applications/{application_id}", response_model=ApplicationOut, summary="Read your application decision")
def application(application_id: str, session: SessionDep, customer: CustomerDep):
    return owned_application(session, customer, application_id)


@router.get("/mortgages", response_model=list[ApplicationOut], summary="List your approved simulated mortgages")
def mortgages(session: SessionDep, customer: CustomerDep):
    return session.scalars(select(MortgageApplication).where(MortgageApplication.customer_id == customer.id,
                           MortgageApplication.status == "approved").order_by(MortgageApplication.id)).all()


@router.get("/mortgages/{mortgage_id}/schedule", response_model=list[Installment], summary="Preview a simulated repayment schedule")
def schedule(mortgage_id: str, session: SessionDep, customer: CustomerDep):
    application = owned_application(session, customer, mortgage_id)
    if application.status != "approved":
        raise HTTPException(409, "Only approved simulated mortgages have repayment schedules")
    return schedule_for(application)


@router.get("/mortgages/{mortgage_id}", response_model=ApplicationOut, summary="Read your approved simulated mortgage")
def mortgage(mortgage_id: str, session: SessionDep, customer: CustomerDep):
    application = owned_application(session, customer, mortgage_id)
    if application.status != "approved":
        raise HTTPException(404, "Approved simulated mortgage not found")
    return application
