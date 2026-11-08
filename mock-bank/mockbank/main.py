"""App factory. The same code becomes a different bank depending on its environment.

Run one bank:   uvicorn mockbank.main:create_app --factory --port 9001
Run another:    BANK_ID=comet BANK_NAME="Comet Card (demo)" \
                uvicorn mockbank.main:create_app --factory --port 9002

Data is seeded once, on first start. To regenerate it, delete data/<bank_id>.db.
"""

from datetime import date

from fastapi import FastAPI
from sqlalchemy import select

from mockbank.api import dev_router, router
from mockbank.config import Settings
from mockbank.db import Base, make_engine, make_sessionmaker
from mockbank.models import Customer
from mockbank.seed import load_seed_file, seed_bank


def create_app(settings: Settings | None = None, *, as_of: date | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.check_safe_to_run()

    engine = make_engine(settings.resolved_database_url)
    Base.metadata.create_all(engine)  # fine for a demo; use Alembic migrations for real apps
    sessions = make_sessionmaker(engine)

    with sessions() as session:
        if session.scalar(select(Customer).limit(1)) is None:  # seed once, on first start
            seed_bank(
                session,
                load_seed_file(settings.customers_file),
                bank_id=settings.bank_id,
                seed=settings.seed,
                history_days=settings.history_days,
                as_of=as_of or date.today(),
            )

    app = FastAPI(
        title=f"{settings.bank_name} API",
        version="1",
        description="Synthetic bank for the Capital Insight demo. Not a real bank.",
    )
    app.state.settings = settings
    app.state.sessionmaker = sessions
    app.include_router(router)
    if settings.dev_mode:
        app.include_router(dev_router)
    return app
