from datetime import timedelta
import logging
import re
from services.mock_mortgage.app.models import Verification
from services.mock_mortgage.app.database import utcnow
from services.mock_mortgage.app.security import issue_token


def request(mortgage_client, caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = mortgage_client.post("/v1/auth/request-code", json={"email": "customer1@mortgages.example.test"})
    assert "code" not in response.json()
    return re.search(r": (\d{6})", caplog.text).group(1)


def test_authentication(mortgage_client, mortgage_headers):
    assert mortgage_client.get("/v1/customers/me").status_code == 401
    headers = mortgage_headers
    assert mortgage_client.get("/v1/customers/me", headers=headers).json()["email"] == "customer1@mortgages.example.test"
    assert mortgage_client.get("/v1/mortgages", headers={"Authorization": headers["Authorization"]+"x"}).status_code == 401


def test_single_use_and_cooldown(mortgage_client, caplog):
    code = request(mortgage_client, caplog)
    body = {"email": "customer1@mortgages.example.test", "code": code}
    assert mortgage_client.post("/v1/auth/request-code", json={"email": body["email"]}).status_code == 429
    assert mortgage_client.post("/v1/auth/verify-code", json=body).status_code == 200
    assert mortgage_client.post("/v1/auth/verify-code", json=body).status_code == 401


def test_wrong_code_attempt_limit(mortgage_client, caplog):
    code = request(mortgage_client, caplog)
    body = {"email": "customer1@mortgages.example.test", "code": "000000" if code != "000000" else "000001"}
    for _ in range(5):
        assert mortgage_client.post("/v1/auth/verify-code", json=body).status_code == 401
    body["code"] = code
    assert mortgage_client.post("/v1/auth/verify-code", json=body).status_code == 401


def test_expired_code(mortgage_client, caplog):
    code = request(mortgage_client, caplog)
    with mortgage_client.app.state.session_factory() as session:
        session.get(Verification, "customer1@mortgages.example.test").expires_at = utcnow()-timedelta(seconds=1)
        session.commit()
    assert mortgage_client.post("/v1/auth/verify-code", json={"email": "customer1@mortgages.example.test", "code": code}).status_code == 401


def test_expired_and_wrong_lender_token(mortgage_client):
    for aud, ttl in [("amex", 100), ("mortgages", -1)]:
        token = issue_token(mortgage_client.app.state.secret, aud, "mortgages-customer-001", ttl)
        assert mortgage_client.get("/v1/mortgages", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unknown_email_and_validation(mortgage_client, caplog):
    with caplog.at_level(logging.WARNING):
        assert mortgage_client.post("/v1/auth/request-code", json={"email": "unknown@example.test"}).status_code == 202
    assert "DEVELOPMENT ONLY" not in caplog.text
    assert mortgage_client.post("/v1/auth/request-code", json={"email": "bad"}).status_code == 422
