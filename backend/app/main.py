"""Capital Insight core API: sessions, consent and aggregation over the mock services.

Run: uvicorn app.main:app --reload --port 8000   (from the backend/ folder)
"""
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from .config import Settings
from .institutions import build_registry
from .routes import banking, connections, lending
from .sessions import SessionStore


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(timeout=settings.upstream_timeout_seconds, transport=transport) as http:
            app.state.http = http
            yield

    app = FastAPI(title="Capital Insight core API", version="0.1.0", lifespan=lifespan,
                  description="Aggregates the mock banks and lenders for one user session. Tokens stay server-side.")
    app.state.settings = settings
    app.state.registry = build_registry(settings)
    app.state.sessions = SessionStore(settings.session_ttl_seconds, settings.max_sessions)

    @app.get("/health", tags=["Health"])
    def health() -> dict:
        return {"status": "ok"}

    for module in (connections, banking, lending):
        app.include_router(module.router)
    return app


app = create_app()
