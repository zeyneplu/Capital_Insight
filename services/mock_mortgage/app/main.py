"""Independent mortgage-specific API: python -m uvicorn app.main:app --port 8006."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import Settings
from .database import Base, make_database
from .models import Metadata
from .seed import seed_mortgages
from .routers import auth, customers, lenders, mortgages


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        engine, factory = make_database(settings.database_url)
        application.state.session_factory = factory
        application.state.engine = engine
        try:
            Base.metadata.create_all(engine)
            with factory() as session:
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                seed_mortgages(session, settings)
                application.state.secret = settings.signing_secret or session.get(Metadata, "signing_secret").value
            yield
        finally:
            engine.dispose()

    application = FastAPI(title="Capital Insight Mock Mortgage Platform", version="1.0.0",
        description="Fictional borrowers, property-based mortgage applications, simulated decisions and repayment previews. No real underwriting, credit checks, disbursements or payments. Monetary values are decimal strings. Authenticate using the mock code flow and Swagger Authorize.",
        lifespan=lifespan, responses={401: {"description": "Missing or invalid token"},
            404: {"description": "Resource unavailable to this customer"}, 422: {"description": "Invalid input"}})
    application.state.settings = settings
    # This service exposes only borrowers, mortgage products, applications and schedules.
    application.include_router(auth.router)
    application.include_router(customers.router)
    application.include_router(mortgages.router)
    application.include_router(lenders.router)
    return application


app = create_app()
