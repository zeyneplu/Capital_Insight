from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app


def test_customer_isolation(client, authorize):
    headers = authorize(client, "customer2@chase.example.test")
    customer = client.get("/v1/customers/me", headers=headers).json()
    assert customer["id"] == "chase-customer-002"
    assert customer["synthetic_identity_id"].startswith("SYNTH-")
    assert customer["created_at"].endswith("Z")
    assert all(a["customer_id"] == customer["id"] for a in client.get("/v1/accounts", headers=headers).json())
    assert client.get("/v1/accounts/chase-customer-001-checking", headers=headers).status_code == 404


def test_cross_instance_token_rejected(client, authorize, tmp_path):
    headers = authorize(client)
    app = create_app(Settings(_env_file=None, bank_id="amex", bank_name="Amex Mock Bank",
                              database_url=f"sqlite:///{tmp_path / 'amex.db'}"))
    with TestClient(app) as other:
        assert other.get("/v1/accounts", headers=headers).status_code == 401
        assert other.get("/health").json()["bank_id"] == "amex"


def test_demo_mode_off(tmp_path, caplog):
    app = create_app(Settings(_env_file=None, demo_mode=False, database_url=f"sqlite:///{tmp_path / 'private.db'}"))
    with TestClient(app) as client:
        response = client.post("/v1/auth/request-code", json={"email": "customer1@chase.example.test"})
        assert response.status_code == 202
        assert "code" not in response.json()
        assert "DEVELOPMENT ONLY" not in caplog.text
