from contextlib import asynccontextmanager
from fastapi import FastAPI
from .config import Settings
from .database import Base, make_database
from .models import Metadata
from .seed import seed_database
from .routers import institutions, customers, accounts, transactions, auth


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        engine, factory = make_database(settings.database_url)
        application.state.engine = engine
        application.state.session_factory = factory
        try:
            Base.metadata.create_all(engine)
            with factory() as session:
                session.connection().exec_driver_sql("BEGIN IMMEDIATE")
                seed_database(session, settings)
                application.state.secret = settings.signing_secret or session.get(Metadata, "signing_secret").value
            yield
        finally:
            engine.dispose()

    application = FastAPI(title=f"{settings.bank_name} ? Capital Insight Mock API", version="1.0.0",
        description="Synthetic banking records for Capital Insight. Mock consent only: no real bank login, email, payments or transfers. Monetary values are decimal strings. Use request-code and verify-code, then paste access_token into Authorize.",
        lifespan=lifespan,
        responses={401: {"description": "Missing or invalid authorization"},
                   404: {"description": "Resource unavailable to this customer"},
                   422: {"description": "Invalid request parameters"}})
    application.state.settings = settings
    for router in (institutions.router, auth.router, customers.router, accounts.router, transactions.router):
        application.include_router(router)
    return application


app = create_app()
