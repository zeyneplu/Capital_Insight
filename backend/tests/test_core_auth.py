"""Application authentication and isolation from other users' institutions."""

import json
from datetime import timedelta

from cryptography.fernet import Fernet
import pytest
from sqlalchemy import select

from backend.app.config import Settings
from backend.app.database import utcnow
from backend.app.models import Connection, SessionToken, User
from backend.app.security import decrypt_token, encrypt_token, hash_token, make_cipher


def test_registration_normalizes_email_and_does_not_return_password(client):
    response = client.post("/v1/auth/register", json={
        "email": " New.User@Example.test ", "password": "correct-horse-2026",
    })
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new.user@example.test"
    assert set(body["user"]) == {"id", "email", "created_at", "email_verified_at"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == client.app.state.settings.session_ttl_seconds
    assert "correct-horse-2026" not in response.text

    with client.app.state.session_factory() as session:
        user = session.get(User, body["user"]["id"])
        assert user.password_hash.startswith("scrypt$")
        assert user.password_hash != "correct-horse-2026"
        assert user.created_at.utcoffset() == timedelta(0)
        token = session.scalar(select(SessionToken).where(SessionToken.user_id == user.id))
        assert token.token_hash == hash_token(body["access_token"])
        assert token.token_hash != body["access_token"]
        assert token.expires_at.utcoffset() == timedelta(0)


def test_duplicate_registration_is_case_insensitive(client):
    payload = {"email": "duplicate@example.test", "password": "correct-horse-2026"}
    assert client.post("/v1/auth/register", json=payload).status_code == 201
    response = client.post("/v1/auth/register", json={**payload, "email": "DUPLICATE@example.test"})
    assert response.status_code == 409


@pytest.mark.parametrize("body", [
    {"email": "person@example.test", "password": "short"},
    {"email": "invalid-address", "password": "correct-horse-2026"},
])
def test_registration_validates_credentials(client, body):
    assert client.post("/v1/auth/register", json=body).status_code == 422


def test_login_returns_new_session_and_rejects_wrong_credentials(client):
    payload = {"email": "signin@example.test", "password": "correct-horse-2026"}
    registration = client.post("/v1/auth/register", json=payload).json()
    response = client.post("/v1/auth/login", json={**payload, "email": "SIGNIN@example.test"})
    assert response.status_code == 200
    assert response.json()["access_token"] != registration["access_token"]
    assert response.json()["user"]["id"] == registration["user"]["id"]
    assert client.post("/v1/auth/login", json={**payload, "password": "wrong-password"}).status_code == 401
    unknown = client.post("/v1/auth/login", json={**payload, "email": "missing@example.test"})
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == "Email or password is incorrect"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer invalid-token"},
                                     {"Authorization": "Basic invalid-token"}])
def test_missing_or_invalid_session_returns_401(client, headers):
    response = client.get("/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_expired_session_is_rejected(client, auth_headers):
    token = auth_headers["Authorization"].split(" ", 1)[1]
    with client.app.state.session_factory() as session:
        record = session.scalar(select(SessionToken).where(SessionToken.token_hash == hash_token(token)))
        record.expires_at = utcnow() - timedelta(seconds=1)
        session.commit()
    assert client.get("/v1/auth/me", headers=auth_headers).status_code == 401


def test_logout_revokes_only_current_session(client):
    payload = {"email": "logout@example.test", "password": "correct-horse-2026"}
    first = client.post("/v1/auth/register", json=payload).json()["access_token"]
    second = client.post("/v1/auth/login", json=payload).json()["access_token"]
    first_headers = {"Authorization": f"Bearer {first}"}
    second_headers = {"Authorization": f"Bearer {second}"}
    response = client.post("/v1/auth/logout", headers=first_headers)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get("/v1/auth/me", headers=first_headers).status_code == 401
    assert client.get("/v1/auth/me", headers=second_headers).status_code == 200


def test_connection_ownership_and_secret_storage(client, auth_headers, other_headers):
    user_id = client.get("/v1/auth/me", headers=auth_headers).json()["id"]
    secret = "upstream-bank-secret-for-alice"
    encrypted = encrypt_token(client.app.state.cipher, secret)
    with client.app.state.session_factory() as session:
        connection = Connection(
            user_id=user_id, provider="chase", kind="mock_bank", remote_id="customer-alice",
            display_name="Chase Mock Bank", encrypted_token=encrypted,
            expires_at=utcnow() + timedelta(minutes=30),
        )
        session.add(connection)
        session.commit()
        connection_id = connection.id
        assert connection.encrypted_token != secret
        assert decrypt_token(client.app.state.cipher, connection.encrypted_token) == secret

    own_list = client.get("/v1/connections", headers=auth_headers)
    assert own_list.status_code == 200
    assert own_list.json()[0]["id"] == connection_id
    assert "encrypted_token" not in own_list.text
    assert secret not in own_list.text
    assert encrypted not in own_list.text
    assert client.get("/v1/connections", headers=other_headers).json() == []
    assert client.delete(f"/v1/connections/{connection_id}", headers=other_headers).status_code == 404
    assert client.get(f"/v1/connections/{connection_id}/offers", headers=other_headers).status_code == 404
    assert client.delete(f"/v1/connections/{connection_id}", headers=auth_headers).status_code == 204


def test_production_requires_explicit_encryption_key():
    settings = Settings(_env_file=None, environment="production", encryption_key=None,
                        database_url="postgresql://capital:secret@db.example.test/capital_insight")
    with pytest.raises(ValueError, match="ENCRYPTION_KEY is required"):
        make_cipher(settings)


def test_configured_encryption_key_is_used_and_secrets_are_redacted():
    key = Fernet.generate_key().decode()
    settings = Settings(_env_file=None, encryption_key=key, plaid_secret="private-plaid-secret")
    cipher = make_cipher(settings)
    encrypted = encrypt_token(cipher, "private-provider-token")
    assert Fernet(key.encode()).decrypt(encrypted.encode()).decode() == "private-provider-token"
    encoded = json.dumps(settings.model_dump(mode="json"))
    assert key not in encoded
    assert "private-plaid-secret" not in encoded


def test_blank_environment_secrets_are_optional():
    settings = Settings(_env_file=None, encryption_key="", plaid_client_id="  ", plaid_secret="")
    assert settings.encryption_key is None
    assert settings.plaid_client_id is None
    assert settings.plaid_secret is None
