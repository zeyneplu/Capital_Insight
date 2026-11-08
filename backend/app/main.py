from contextlib import asynccontextmanager
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .config import Settings
from .database import Base, make_database
from .security import make_cipher
from .routers import auth, connections, portfolio, plaid


def create_app(settings: Settings | None = None, http_client: httpx.AsyncClient | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        engine, factory = make_database(settings.database_url)
        application.state.engine = engine
        application.state.session_factory = factory
        application.state.settings = settings
        application.state.cipher = make_cipher(settings)
        application.state.http_client = http_client or httpx.AsyncClient(timeout=settings.request_timeout_seconds, follow_redirects=False)
        try:
            Base.metadata.create_all(engine)
            yield
        finally:
            if http_client is None:
                await application.state.http_client.aclose()
            engine.dispose()

    application = FastAPI(title="Capital Insight Core API", version="1.0.0",
        description="User-owned connections, mock financial service aggregation, and Plaid Sandbox integration. Register/login, authorize Swagger with the application token, then link individual providers. Upstream access tokens remain encrypted server-side.",
        lifespan=lifespan)
    application.state.settings = settings
    application.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
        allow_credentials=False, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"])

    @application.get("/health", tags=["Health"], summary="Check core API and application database")
    def health(request: Request):
        with request.app.state.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "service": "capital_insight", "plaid_configured": bool(settings.plaid_client_id and settings.plaid_secret)}

    for router in (auth.router, connections.router, portfolio.router, plaid.router):
        application.include_router(router)
    return application


app = create_app()
