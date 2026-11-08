"""SQLAlchemy setup with PostgreSQL and a convenient local SQLite fallback."""

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator

from .config import BACKEND_ROOT


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Always return aware UTC values, including when SQLite drops time zones."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    pass


def make_database(database_url: str):
    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    parsed = make_url(database_url)
    if parsed.drivername == "postgresql":
        parsed = parsed.set(drivername="postgresql+psycopg")
    options = {"pool_pre_ping": True}
    if parsed.get_backend_name() == "sqlite":
        options["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if not parsed.database or parsed.database == ":memory:":
            options["poolclass"] = StaticPool
        else:
            path = Path(parsed.database)
            if not path.is_absolute():
                path = BACKEND_ROOT / path
            path = path.resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            parsed = parsed.set(database=str(path))
    engine = create_engine(parsed, **options)
    if parsed.get_backend_name() == "sqlite":

        @event.listens_for(engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine, sessionmaker(bind=engine, expire_on_commit=False)
