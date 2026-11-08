from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import Settings
from .database import Base, make_database
from .security import make_cipher
from .migrations import upgrade_schema
from .routers import auth, connections, portfolio, plaid, credit, planning
from .institutions import build_registry
from .sessions import SessionStore
from .routes import banking as frontend_banking, connections as frontend_connections, lending as frontend_lending


def create_app(settings: Settings | None = None,
               transport: httpx.AsyncBaseTransport | httpx.AsyncClient | None = None,
               http_client: httpx.AsyncClient | None = None) -> FastAPI:
    # Accept both commits' test-injection interfaces without changing callers.
    if isinstance(transport, httpx.AsyncClient):
        if http_client is not None:
            raise ValueError("Provide one HTTP client")
        http_client, transport = transport, None
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        engine, factory = make_database(
            settings.database_url, sslmode=settings.database_sslmode, sslrootcert=settings.database_sslrootcert,
            pool_size=settings.database_pool_size, max_overflow=settings.database_max_overflow,
            pool_recycle=settings.database_pool_recycle_seconds,
            connect_timeout=settings.database_connect_timeout_seconds)
        application.state.engine = engine
        application.state.session_factory = factory
        application.state.settings = settings
        application.state.cipher = make_cipher(settings)
        application.state.http_client = http_client or httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=False, transport=transport)
        application.state.http = application.state.http_client
        try:
            Base.metadata.create_all(engine)
            upgrade_schema(engine)
            yield
        finally:
            if http_client is None:
                await application.state.http_client.aclose()
            engine.dispose()

    application = FastAPI(title="Capital Insight Core API", version="1.0.0",
        description="User-owned connections, mock financial service aggregation, and Plaid Sandbox integration. Register/login, authorize Swagger with the application token, then link individual providers. Upstream access tokens remain encrypted server-side.",
        lifespan=lifespan)
    application.state.settings = settings
    application.state.registry = build_registry(settings)
    application.state.sessions = SessionStore(settings.session_ttl_seconds, settings.max_sessions)
    application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
        allow_credentials=False, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Session-Id"])

    @application.get("/health", tags=["Health"], summary="Check core API and application database")
    def health(request: Request):
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "service": "capital_insight", "plaid_configured": bool(settings.plaid_client_id and settings.plaid_secret)}

    for router in (frontend_connections.router, frontend_banking.router, frontend_lending.router,
                   auth.router, connections.router, portfolio.router, plaid.router, credit.router, planning.router):
        application.include_router(router)
    return application


app = create_app()
