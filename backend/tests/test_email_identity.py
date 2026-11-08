"""Email ownership is required before bank linking, with durable user identity."""
from datetime import timedelta
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import select
from backend.app.main import create_app
from backend.app.config import Settings
from backend.app.models import User, EmailChallenge, Connection
from backend.app.database import utcnow


@pytest.fixture
def identity(tmp_path, monkeypatch):
    from backend.app.routers import auth
    sent = []
    fail = {"value":False}
    def send(settings, email, code, ttl):
        if fail["value"]:
            from backend.app.mailer import MailDeliveryError
            raise MailDeliveryError()
        sent.append((email,code))
    monkeypatch.setattr(auth,"send_user_code",send)
    settings = Settings(_env_file=None,database_url=f"sqlite:///{tmp_path / 'identity.db'}",
        encryption_key=Fernet.generate_key().decode(),mock_email_recipient_mode="forwarded_demo", auth_code_delivery="smtp",
        smtp_username="sender@gmail.com",smtp_password="private-app-password",smtp_from="sender@gmail.com",
        auth_email_recipient="shared-inbox@example.test",mock_service_api_key="internal-secret")
    calls=[]
    def upstream(request):
        calls.append(request)
        return httpx.Response(202,json={"message":"Verification email requested", "delivery":"email"})
    http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    with TestClient(create_app(settings,http_client=http)) as client:
        client.app.state.email_upstream_calls=calls
        yield client,settings,sent,fail
    import asyncio
    asyncio.run(http.aclose())


def verify(client,sent,email="owner@example.com"):
    assert client.post("/v1/auth/request-email-code",json={"email":email}).status_code == 202
    return client.post("/v1/auth/verify-email-code",json={"email":email,"code":sent[-1][1]})


def test_own_email_unique_identity_and_single_use(identity):
    client,_,sent,_ = identity
    response = verify(client,sent," Owner@Example.com ")
    assert response.status_code == 200,response.text
    body = response.json()
    assert sent[0][0] == "owner@example.com" # never redirected to the old shared demo inbox
    assert body["user"]["email_verified_at"]
    assert body["user"]["email"] == "owner@example.com"
    assert client.post("/v1/auth/verify-email-code",json={"email":"owner@example.com","code":sent[0][1]}).status_code == 401
    headers = {"Authorization":f"Bearer {body['access_token']}"}
    assert client.get("/v1/connections",headers=headers).status_code == 200
    assert client.post("/api/v1/sessions",headers=headers).status_code == 201
    with client.app.state.session_factory() as database:
        users = database.scalars(select(User)).all()
        assert len(users) == 1 and users[0].email == "owner@example.com"
        challenge = database.get(EmailChallenge,"owner@example.com")
        assert sent[0][1] not in challenge.encrypted_code and challenge.used


def test_unverified_and_anonymous_sessions_cannot_connect(identity):
    client,_,_,_ = identity
    token = client.post("/v1/auth/register",json={"email":"new@example.com","password":"some-valid-password"}).json()["access_token"]
    headers = {"Authorization":f"Bearer {token}"}
    assert client.post("/v1/plaid/link-token",headers=headers).status_code == 403
    assert client.post("/v1/connections/chase/request-code",headers=headers,json={"email":"customer1@chase.example.test"}).status_code == 403
    assert client.post("/api/v1/sessions",headers=headers).status_code == 403
    session_id = client.post("/api/v1/sessions").json()["session_id"]
    assert client.post("/api/v1/institutions/chase/request-code",headers={"X-Session-Id":session_id},json={"email":"customer1@chase.example.test"}).status_code == 403


def test_wrong_email_code_attempts_cooldown_expiry(identity):
    client,_,sent,_ = identity
    email = "owner@example.com"
    client.post("/v1/auth/request-email-code",json={"email":email})
    assert client.post("/v1/auth/request-email-code",json={"email":email}).status_code == 429
    wrong = "000000" if sent[0][1] != "000000" else "000001"
    for _ in range(5):
        assert client.post("/v1/auth/verify-email-code",json={"email":email,"code":wrong}).status_code == 401
    assert client.post("/v1/auth/verify-email-code",json={"email":email,"code":sent[0][1]}).status_code == 401
    with client.app.state.session_factory() as db:
        assert db.scalar(select(User)) is None
        record = db.get(EmailChallenge,email)
        record.requested_at -= timedelta(minutes=10)
        db.commit()
    client.post("/v1/auth/request-email-code",json={"email":email})
    with client.app.state.session_factory() as db:
        db.get(EmailChallenge,email).expires_at -= timedelta(days=1)
        db.commit()
    assert client.post("/v1/auth/verify-email-code",json={"email":email,"code":sent[-1][1]}).status_code == 401


def test_delivery_failure_never_creates_user_or_active_challenge(identity):
    client,_,_,fail = identity
    fail["value"] = True
    assert client.post("/v1/auth/request-email-code",json={"email":"owner@example.com"}).status_code == 503
    with client.app.state.session_factory() as db:
        assert db.scalar(select(User)) is None and db.get(EmailChallenge,"owner@example.com") is None


def test_password_account_reuses_identity_after_email_verification(identity):
    client,_,sent,_ = identity
    original = client.post("/v1/auth/register",json={"email":"owner@example.com","password":"some-valid-password"}).json()["user"]
    verified = verify(client,sent).json()
    assert original["id"] == verified["user"]["id"]
    with client.app.state.session_factory() as db:
        assert len(db.scalars(select(User)).all()) == 1


def test_logout_invalidates_frontend_session(identity):
    client,_,sent,_ = identity
    token = verify(client,sent).json()["access_token"]
    headers={"Authorization":f"Bearer {token}"}
    sid=client.post("/api/v1/sessions",headers=headers).json()["session_id"]
    assert client.get("/api/v1/institutions",headers={"X-Session-Id":sid}).status_code == 200
    client.post("/v1/auth/logout",headers=headers)
    assert client.get("/api/v1/institutions",headers={"X-Session-Id":sid}).status_code == 401


def test_old_database_is_upgraded_without_losing_users(tmp_path):
    import sqlite3
    path=tmp_path/"old.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY, email VARCHAR(254) UNIQUE, password_hash TEXT, created_at TIMESTAMP)")
        db.execute("INSERT INTO users VALUES ('old-id','existing@example.com','old-hash','2026-11-01 00:00:00')")
        db.execute("CREATE TABLE connections (id VARCHAR(36) PRIMARY KEY,user_id VARCHAR(36), provider VARCHAR(64),kind VARCHAR(32),remote_id VARCHAR(255),display_name VARCHAR(255),encrypted_token TEXT,expires_at TIMESTAMP,created_at TIMESTAMP)")
    settings=Settings(_env_file=None,database_url=f"sqlite:///{path}",encryption_key=Fernet.generate_key().decode())
    for _ in range(2):
        with TestClient(create_app(settings)) as client:
            with client.app.state.session_factory() as db:
                user=db.get(User,"old-id")
                assert user.email == "existing@example.com" and user.email_verified_at is None


def test_only_verified_owner_can_choose_the_delivery_email(identity):
    import json
    client,_,sent,_=identity
    token=verify(client,sent,"owner@example.com").json()["access_token"]
    bearer={"Authorization":f"Bearer {token}"}
    sid=client.post("/api/v1/sessions",headers=bearer).json()["session_id"]
    for endpoint,headers in [("/v1/connections/chase/request-code",bearer),
        ("/api/v1/institutions/chase/request-code",{"X-Session-Id":sid})]:
        response=client.post(endpoint,headers=headers,json={"email":"customer1@chase.example.test","delivery_email":"attacker@example.com"})
        assert response.status_code == 202,response.text
        upstream=client.app.state.email_upstream_calls[-1]
        assert json.loads(upstream.content)["delivery_email"] == "owner@example.com"
        assert upstream.headers["X-Internal-Key"] == "internal-secret"
        assert "internal-secret" not in response.text


@pytest.mark.parametrize("email",["first,second@example.com","x@example.com;other@example.com","Name <owner@example.com>","owner@example.com\r\nBcc: hidden@example.com"])
def test_personal_sign_in_requires_one_email_address(identity,email):
    client,_,sent,_=identity
    assert client.post("/v1/auth/request-email-code",json={"email":email}).status_code == 422
    assert sent == []
