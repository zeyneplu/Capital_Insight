from datetime import timedelta
import logging
import re
from app.models import Verification
from app.database import utcnow
from app.security import issue_token


def request(client, caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = client.post("/v1/auth/request-code", json={"email": "customer1@chase.example.test"})
    assert "code" not in response.json()
    return re.search(r": (\d{6})", caplog.text).group(1)


def test_authentication(client, authorize):
    assert client.get("/v1/customers/me").status_code == 401
    headers = authorize(client)
    assert client.get("/v1/customers/me", headers=headers).json()["email"] == "customer1@chase.example.test"
    assert client.get("/v1/accounts", headers={"Authorization": headers["Authorization"]+"x"}).status_code == 401


def test_single_use_and_cooldown(client, caplog):
    code = request(client, caplog)
    body = {"email": "customer1@chase.example.test", "code": code}
    assert client.post("/v1/auth/request-code", json={"email": body["email"]}).status_code == 429
    assert client.post("/v1/auth/verify-code", json=body).status_code == 200
    assert client.post("/v1/auth/verify-code", json=body).status_code == 401


def test_wrong_code_attempt_limit(client, caplog):
    code = request(client, caplog)
    body = {"email": "customer1@chase.example.test", "code": "000000" if code != "000000" else "000001"}
    for _ in range(5):
        assert client.post("/v1/auth/verify-code", json=body).status_code == 401
    body["code"] = code
    assert client.post("/v1/auth/verify-code", json=body).status_code == 401


def test_expired_code(client, bank, caplog):
    code = request(client, caplog)
    with bank.state.session_factory() as session:
        session.get(Verification, "customer1@chase.example.test").expires_at = utcnow()-timedelta(seconds=1)
        session.commit()
    assert client.post("/v1/auth/verify-code", json={"email": "customer1@chase.example.test", "code": code}).status_code == 401


def test_expired_and_wrong_bank_token(client, bank):
    for aud, ttl in [("amex", 100), ("chase", -1)]:
        token = issue_token(bank.state.secret, aud, "chase-customer-001", ttl)
        assert client.get("/v1/accounts", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unknown_email_and_validation(client, caplog):
    with caplog.at_level(logging.WARNING):
        assert client.post("/v1/auth/request-code", json={"email": "unknown@example.test"}).status_code == 202
    assert "DEVELOPMENT ONLY" not in caplog.text
    assert client.post("/v1/auth/request-code", json={"email": "bad"}).status_code == 422
