import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import logging
import re
import pytest
from fastapi.testclient import TestClient
from services.mock_loan.app.main import create_app
from services.mock_loan.app.config import Settings

@pytest.fixture
def loan_client(tmp_path):
    app = create_app(Settings(_env_file=None, demo_mode=True, database_url=f"sqlite:///{tmp_path / 'loans.db'}"))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def loan_headers(loan_client, caplog):
    email = "customer1@loans.example.test"
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        assert loan_client.post("/v1/auth/request-code", json={"email": email}).status_code == 202
    code = re.search(r": (\d{6})", caplog.text).group(1)
    token = loan_client.post("/v1/auth/verify-code", json={"email": email, "code": code}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


