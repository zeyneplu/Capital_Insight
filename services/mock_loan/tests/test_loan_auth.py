from datetime import timedelta
import logging
import re
from services.mock_loan.app.models import Verification
from services.mock_loan.app.database import utcnow
from services.mock_loan.app.security import issue_token


def request(loan_client, caplog):
    with caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = loan_client.post("/v1/auth/request-code", json={"email": "customer1@loans.example.test"})
    assert "code" not in response.json()
    return re.search(r": (\d{6})", caplog.text).group(1)


def test_authentication(loan_client, loan_headers):
    assert loan_client.get("/v1/customers/me").status_code == 401
    headers = loan_headers
    assert loan_client.get("/v1/customers/me", headers=headers).json()["email"] == "customer1@loans.example.test"
    assert loan_client.get("/v1/loans", headers={"Authorization": headers["Authorization"]+"x"}).status_code == 401


def test_single_use_and_cooldown(loan_client, caplog):
    code = request(loan_client, caplog)
    body = {"email": "customer1@loans.example.test", "code": code}
    assert loan_client.post("/v1/auth/request-code", json={"email": body["email"]}).status_code == 429
    assert loan_client.post("/v1/auth/verify-code", json=body).status_code == 200
    assert loan_client.post("/v1/auth/verify-code", json=body).status_code == 401


def test_wrong_code_attempt_limit(loan_client, caplog):
    code = request(loan_client, caplog)
    body = {"email": "customer1@loans.example.test", "code": "000000" if code != "000000" else "000001"}
    for _ in range(5):
        assert loan_client.post("/v1/auth/verify-code", json=body).status_code == 401
    body["code"] = code
    assert loan_client.post("/v1/auth/verify-code", json=body).status_code == 401


def test_expired_code(loan_client, caplog):
    code = request(loan_client, caplog)
    with loan_client.app.state.session_factory() as session:
        session.get(Verification, "customer1@loans.example.test").expires_at = utcnow()-timedelta(seconds=1)
        session.commit()
    assert loan_client.post("/v1/auth/verify-code", json={"email": "customer1@loans.example.test", "code": code}).status_code == 401


def test_expired_and_wrong_lender_token(loan_client):
    for aud, ttl in [("amex", 100), ("loans", -1)]:
        token = issue_token(loan_client.app.state.secret, aud, "loans-customer-001", ttl)
        assert loan_client.get("/v1/loans", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unknown_email_and_validation(loan_client, caplog):
    with caplog.at_level(logging.WARNING):
        assert loan_client.post("/v1/auth/request-code", json={"email": "unknown@example.test"}).status_code == 202
    assert "DEVELOPMENT ONLY" not in caplog.text
    assert loan_client.post("/v1/auth/request-code", json={"email": "bad"}).status_code == 422
