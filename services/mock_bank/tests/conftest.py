import logging
import re
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import Settings
from app.main import create_app


@pytest.fixture
def bank(tmp_path):
    return create_app(Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'bank.db'}", demo_mode=True))


@pytest.fixture
def client(bank):
    with TestClient(bank) as client:
        yield client


@pytest.fixture
def authorize(caplog):
    def login(client, email="customer1@chase.example.test"):
        with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
            response = client.post("/v1/auth/request-code", json={"email": email})
        assert response.status_code == 202
        code = re.search(r"DEVELOPMENT ONLY mock consent code for "+re.escape(email)+r": (\d{6})", caplog.text).group(1)
        token = client.post("/v1/auth/verify-code", json={"email": email, "code": code}).json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return login
