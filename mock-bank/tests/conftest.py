import re
from collections.abc import Callable
from datetime import date

import pytest
from fastapi.testclient import TestClient

from mockbank.config import Settings
from mockbank.main import create_app

AS_OF = date(2026, 11, 7)
ALEX = {"email": "alex.rivera@example.com", "ssn_last4": "4821"}
JORDAN = {"email": "jordan.lee@example.com", "ssn_last4": "1937"}


def make_settings(**overrides) -> Settings:
    base = {"_env_file": None, "database_url": "sqlite://", "bank_id": "pecan"}
    return Settings(**(base | overrides))


@pytest.fixture
def make_client() -> Callable[..., TestClient]:
    def factory(**overrides) -> TestClient:
        return TestClient(create_app(make_settings(**overrides), as_of=AS_OF))

    return factory


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()


def latest_code(client: TestClient, email: str) -> str:
    messages = client.get("/dev/outbox", params={"email": email}).json()
    return re.search(r"\b(\d{6})\b", messages[0]["body"]).group(1)


def connect(client: TestClient, person: dict) -> str:
    """Full consent flow -> access token."""
    consent = client.post("/v1/consents", json=person).json()
    code = latest_code(client, person["email"])
    resp = client.post(f"/v1/consents/{consent['consent_id']}/token", json={"code": code})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
