"""Judge/tester access: one configured email gets a fixed code; everyone else is unchanged."""
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from services.mock_bank.app.config import Settings as BankSettings
from services.mock_bank.app.main import create_app as create_bank
from services.mock_bank.app.security import token_customer

CODE = "482913"


def core(tmp_path, **overrides):
    values = dict(_env_file=None, database_url=f"sqlite:///{tmp_path / 'tester.db'}", encryption_key=Fernet.generate_key().decode(),
                  tester_email="test@email.com", tester_code=CODE)
    return TestClient(create_app(Settings(**{**values, **overrides})))


def test_tester_signs_in_without_email_and_code_rules_still_apply(tmp_path):
    with core(tmp_path) as client:
        requested = client.post("/v1/auth/request-email-code", json={"email": " Test@Email.com "})
        assert requested.status_code == 202 and requested.json()["delivery"] == "tester"
        assert client.post("/v1/auth/verify-email-code", json={"email": "test@email.com", "code": "000000"}).status_code == 401
        signed_in = client.post("/v1/auth/verify-email-code", json={"email": "test@email.com", "code": CODE})
        assert signed_in.status_code == 200 and signed_in.json()["user"]["email_verified_at"]
        # Single use: the same challenge cannot be replayed.
        assert client.post("/v1/auth/verify-email-code", json={"email": "test@email.com", "code": CODE}).status_code == 401


def test_other_emails_never_get_the_tester_code(tmp_path):
    with core(tmp_path) as client:
        # No SMTP configured: ordinary sign-in still requires real email delivery.
        assert client.post("/v1/auth/request-email-code", json={"email": "someone@example.com"}).status_code == 503
        assert client.post("/v1/auth/verify-email-code", json={"email": "someone@example.com", "code": CODE}).status_code == 401


def test_tester_access_is_disabled_in_production(tmp_path):
    from backend.app.routers.auth import is_tester
    production = Settings(_env_file=None, environment="production", database_url="postgresql://u:p@db.example.test/x",
                          tester_email="test@email.com", tester_code=CODE)
    assert not is_tester(production, "test@email.com")
    assert not is_tester(Settings(_env_file=None, tester_email="test@email.com"), "test@email.com")  # code missing


def test_mock_institution_tester_code_and_longer_consent(tmp_path):
    email = "customer1@pnc.example.test"
    settings = BankSettings(_env_file=None, bank_id="pnc", database_url=f"sqlite:///{tmp_path / 'pnc.db'}", demo_mode=True,
                            tester_email=email, tester_code=CODE, tester_token_ttl_seconds=7200)
    with TestClient(create_bank(settings)) as bank:
        assert bank.post("/v1/auth/request-code", json={"email": email}).json()["delivery"] == "tester"
        token = bank.post("/v1/auth/verify-code", json={"email": email, "code": CODE})
        assert token.status_code == 200 and token.json()["expires_in"] == 7200
        assert token_customer(bank.app.state.secret, "pnc", token.json()["access_token"]) == "pnc-customer-001"


def test_mock_tester_code_requires_demo_mode(tmp_path):
    email = "customer1@pnc.example.test"
    settings = BankSettings(_env_file=None, bank_id="pnc", database_url=f"sqlite:///{tmp_path / 'pnc.db'}", demo_mode=False,
                            tester_email=email, tester_code=CODE)
    with TestClient(create_bank(settings)) as bank:
        assert bank.post("/v1/auth/request-code", json={"email": email}).json()["delivery"] != "tester"
        assert bank.post("/v1/auth/verify-code", json={"email": email, "code": CODE}).status_code == 401
