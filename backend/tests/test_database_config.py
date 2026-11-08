"""PostgreSQL/RDS URL handling and the production storage guard (no database needed)."""
import pytest
from pydantic import ValidationError

from backend.app.config import Settings
from backend.app.database import postgres_url

RDS = "postgresql://capital:secret@ci.abc123.us-east-1.rds.amazonaws.com:5432/capital_insight"


def test_rds_defaults_to_tls_and_psycopg3():
    url = postgres_url(RDS)
    assert url.drivername == "postgresql+psycopg"
    assert url.query["sslmode"] == "require"


def test_explicit_tls_settings_win():
    url = postgres_url(RDS + "?sslmode=disable", "verify-full", "certs/global-bundle.pem")
    assert url.query["sslmode"] == "verify-full"
    assert url.query["sslrootcert"].endswith("global-bundle.pem")
    assert postgres_url(RDS + "?sslmode=verify-ca").query["sslmode"] == "verify-ca"


def test_heroku_style_scheme_and_local_hosts():
    assert postgres_url("postgres://u:p@localhost/db").drivername == "postgresql+psycopg"
    assert "sslmode" not in postgres_url("postgresql://u:p@localhost/db").query
    assert postgres_url("sqlite:///./x.db").get_backend_name() == "sqlite"


def test_production_requires_postgres():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", database_url="sqlite:///./x.db")
    assert Settings(_env_file=None, environment="production", database_url=RDS).database_url == RDS
