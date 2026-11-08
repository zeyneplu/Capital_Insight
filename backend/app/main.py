"""App factory: wires config -> data source -> LLM client -> routes.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs   (OpenAPI schema at /openapi.json)
"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import AsyncOpenAI

from app.api.routes import router
from app.config import Settings, get_settings
from app.domain.errors import InvalidRequestError, NotFoundError
from app.sources.bank_api import BankApiClient, BankAuthError, BankUnavailableError
from app.sources.fixtures import FixtureSource
from app.sources.nessie import NessieError, NessieSource


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One shared HTTP connection pool for the app's lifetime, closed on shutdown.
        async with httpx.AsyncClient(base_url=settings.nessie_base_url, timeout=10) as http:
            if settings.data_source == "nessie":
                if not settings.nessie_api_key:  # catches both missing and "NESSIE_API_KEY="
                    raise RuntimeError("DATA_SOURCE=nessie requires NESSIE_API_KEY")
                app.state.source = NessieSource(http, settings.nessie_api_key.get_secret_value())
            else:
                app.state.source = FixtureSource()

            app.state.llm = (
                AsyncOpenAI(
                    base_url=settings.nvidia_base_url,
                    api_key=settings.nvidia_api_key.get_secret_value(),
                    timeout=60,
                )
                if settings.nvidia_api_key
                else None
            )
            app.state.settings = settings

            async with AsyncExitStack() as stack:
                app.state.banks = {
                    bank_id: BankApiClient(
                        await stack.enter_async_context(
                            httpx.AsyncClient(base_url=cfg.base_url, timeout=10)
                        ),
                        institution=cfg.name,
                    )
                    for bank_id, cfg in settings.banks.items()
                }
                yield

    app = FastAPI(title="Capital Insight API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    # Domain errors -> HTTP, in one place.
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidRequestError)
    async def _invalid(_: Request, exc: InvalidRequestError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(BankAuthError)
    async def _bank_auth(_: Request, exc: BankAuthError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc), "reconnect": True})

    @app.exception_handler(NessieError)
    @app.exception_handler(BankUnavailableError)
    async def _upstream(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    app.include_router(router)
    return app


app = create_app()
