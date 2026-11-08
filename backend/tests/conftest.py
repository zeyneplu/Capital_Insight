from pathlib import Path
import sys
import asyncio
import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.app.config import Settings
from backend.app.main import create_app


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'core.db'}",
                    encryption_key=Fernet.generate_key().decode(), plaid_client_id=None, plaid_secret=None)


@pytest.fixture
def client(settings):
    upstream = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    with TestClient(create_app(settings, http_client=upstream)) as client:
        yield client
    asyncio.run(upstream.aclose())


def register(client, email):
    response = client.post("/v1/auth/register", json={"email": email, "password": "hackathon-password-2026"})
    assert response.status_code == 201, response.text
    from backend.app.models import User
    from backend.app.database import utcnow
    from sqlalchemy import select
    with client.app.state.session_factory() as database:
        for user in database.scalars(select(User)):
            user.email_verified_at = utcnow()
        database.commit()

    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def auth_headers(client):
    return register(client, "alice@example.test")


@pytest.fixture
def other_headers(client):
    return register(client, "bob@example.test")
