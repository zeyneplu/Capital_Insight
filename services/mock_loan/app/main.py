"""Independent loan-specific API: python -m uvicorn app.main:app --port 8005."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .credit import upgrade_credit_schema
from .config import Settings
from .database import Base, make_database
from .models import Metadata
from .seed import seed_loans
from .routers import auth, customers, lenders, loans


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        engine, factory = make_database(settings.database_url)
        application.state.session_factory = factory
        application.state.engine = engine
        try:
            Base.metadata.create_all(engine)
            upgrade_credit_schema(engine)
            with factory() as session:
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                seed_loans(session, settings)
                application.state.secret = settings.signing_secret or session.get(Metadata, "signing_secret").value
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Capital Insight Mock Loan Platform", version="1.0.0",
        description="Fictional customers, loan offers, simulated decisions and repayment previews. No real underwriting, credit checks, disbursements or payments. Monetary values are decimal strings. Authenticate using the mock code flow and Swagger Authorize.",
        lifespan=lifespan, responses={401: {"description": "Missing or invalid token"},
            404: {"description": "Resource unavailable to this customer"}, 422: {"description": "Invalid input"}})
    application.state.settings = settings
    # This service exposes only borrowers, loan products, applications and schedules.
    application.include_router(auth.router)
    application.include_router(customers.router)
    application.include_router(loans.router)
    application.include_router(lenders.router)
    return application


app = create_app()
