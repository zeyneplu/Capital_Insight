"""Real consent state transitions with an SMTP stand-in, never real emails."""
import importlib
import re
import smtplib
from datetime import timedelta
from fastapi.testclient import TestClient
import pytest


@pytest.fixture(params=["mock_bank", "mock_loan", "mock_mortgage"])
def mail_context(request, tmp_path, monkeypatch):
    prefix = f"services.{request.param}.app"
    config = importlib.import_module(prefix+".config")
    main = importlib.import_module(prefix+".main")
    models = importlib.import_module(prefix+".models")
    mail = importlib.import_module(prefix+".mail")
    sent = []
    commands = []
    state = {"fail": False}
    class SMTP:
        def __init__(self, *args, **kwargs):
            commands.append(("connect", args, kwargs))
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def ehlo(self):
            commands.append(("ehlo",))
        def starttls(self, **kwargs):
            assert kwargs["context"].check_hostname
            commands.append(("tls",))
        def login(self, username, password):
            assert username == "sender@gmail.com" and password == "test-app-password"
            commands.append(("login",))
        def send_message(self, message):
            if state["fail"]:
                raise smtplib.SMTPAuthenticationError(535, b"never-return-this-private-provider-message")
            sent.append(message)
            return {}
    monkeypatch.setattr(mail.smtplib, "SMTP", SMTP)
    monkeypatch.setattr(mail.smtplib, "SMTP_SSL", SMTP)
    settings = config.Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'email.db'}", demo_mode=True,
        mock_email_recipient_mode="forwarded_demo", auth_code_delivery="smtp", smtp_username="sender@gmail.com", smtp_password="test-app-password",
        smtp_from="sender@gmail.com", auth_email_recipient="inbox@example.com")
    with TestClient(main.create_app(settings)) as client:
        yield client, settings, models, sent, commands, state


def email_for(settings):
    return f"customer1@{getattr(settings, 'bank_id', getattr(settings, 'lender_id', ''))}.example.test"


def test_smtp_code_authentication(mail_context, caplog):
    client, settings, models, sent, commands, _ = mail_context
    email = email_for(settings)
    response = client.post("/v1/auth/request-code", json={"email": email})
    assert response.status_code == 202
    assert response.json()["delivery"] == "email"
    assert len(sent) == 1
    assert sent[0]["To"] == "inbox@example.com"
    assert sent[0]["From"] == "sender@gmail.com"
    code = re.search(r"verification code is: (\d{6})", sent[0].get_content()).group(1)
    assert code not in response.text and code not in caplog.text
    assert "DEVELOPMENT ONLY" not in caplog.text
    assert [c[0] for c in commands].index("tls") < [c[0] for c in commands].index("login")
    with client.app.state.session_factory() as session:
        record = session.get(models.Verification, email)
        assert record.code_hash != code and record.expires_at.tzinfo is not None
    assert client.post("/v1/auth/verify-code", json={"email": email, "code": code}).status_code == 200
    assert client.post("/v1/auth/verify-code", json={"email": email, "code": code}).status_code == 401
    assert client.post("/v1/auth/request-code", json={"email": email}).status_code == 429
    assert len(sent) == 1


def test_unknown_identity_never_emails(mail_context):
    client, _, _, sent, _, _ = mail_context
    response = client.post("/v1/auth/request-code", json={"email": "unknown@example.com"})
    assert response.status_code == 202 and response.json()["delivery"] == "email"
    assert sent == []


def test_smtp_failure_is_retryable_without_activating_code(mail_context):
    client, settings, models, sent, _, state = mail_context
    email = email_for(settings)
    state["fail"] = True
    response = client.post("/v1/auth/request-code", json={"email": email})
    assert response.status_code == 503
    assert "never-return-this" not in response.text and "test-app-password" not in response.text
    with client.app.state.session_factory() as session:
        assert session.get(models.Verification, email) is None
    state["fail"] = False
    assert client.post("/v1/auth/request-code", json={"email": email}).status_code == 202
    assert len(sent) == 1


def test_missing_config_is_clear_and_does_not_fall_back_to_logs(mail_context, caplog):
    client, settings, _, sent, _, _ = mail_context
    settings.smtp_password = None
    response = client.post("/v1/auth/request-code", json={"email": email_for(settings)})
    assert response.status_code == 503
    assert sent == [] and "DEVELOPMENT ONLY" not in caplog.text


def test_ssl_does_not_starttls(mail_context):
    client, settings, _, sent, commands, _ = mail_context
    settings.smtp_security = "ssl"
    settings.smtp_port = 465
    assert client.post("/v1/auth/request-code", json={"email": email_for(settings)}).status_code == 202
    assert len(sent) == 1 and "tls" not in [c[0] for c in commands]
    assert commands[0][2]["context"].check_hostname


def test_smtp_code_still_expires(mail_context):
    client, settings, models, sent, _, _ = mail_context
    email = email_for(settings)
    client.post("/v1/auth/request-code", json={"email": email})
    code = re.search(r"verification code is: (\d{6})", sent[0].get_content()).group(1)
    with client.app.state.session_factory() as session:
        record = session.get(models.Verification, email)
        record.expires_at = record.expires_at-timedelta(days=1)
        session.commit()
    assert client.post("/v1/auth/verify-code", json={"email": email, "code": code}).status_code == 401


def test_core_interfaces_preserve_email_delivery_and_failure(settings):
    import asyncio
    import httpx
    from backend.app.main import create_app
    state = {"status": 202}
    def upstream(request):
        return httpx.Response(state["status"], json={"message": "If registered, email sent.", "delivery": "email"} if state["status"] == 202 else {"detail": "Could not send verification email"})
    http = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    with TestClient(create_app(settings, http_client=http)) as client:
        app_token = client.post("/v1/auth/register", json={"email":"mailuser@example.test", "password":"email-test-password"}).json()["access_token"]
        from backend.app.models import User
        from backend.app.database import utcnow
        from sqlalchemy import select
        with client.app.state.session_factory() as database:
            database.scalar(select(User)).email_verified_at = utcnow()
            database.commit()
        session_id = client.post("/api/v1/sessions",headers={"Authorization":f"Bearer {app_token}"}).json()["session_id"]
        endpoints = [("/v1/connections/chase/request-code", {"Authorization": f"Bearer {app_token}"}),
                     ("/api/v1/institutions/chase/request-code", {"X-Session-Id": session_id})]
        for endpoint, headers in endpoints:
            response = client.post(endpoint, json={"email":"customer1@chase.example.test"}, headers=headers)
            assert response.status_code == 202 and response.json()["delivery"] == "email"
        state["status"] = 503
        for endpoint, headers in endpoints:
            assert client.post(endpoint, json={"email":"customer1@chase.example.test"}, headers=headers).status_code == 503
    asyncio.run(http.aclose())


def test_recipient_override_requires_internal_key(mail_context):
    from pydantic import SecretStr
    client,settings,_,sent,_,_ = mail_context
    email=email_for(settings)
    body={"email":email,"delivery_email":"verified-owner@example.com"}
    assert client.post("/v1/auth/request-code",json=body).status_code == 403
    assert sent == []
    settings.mock_service_api_key=SecretStr("internal-secret")
    assert client.post("/v1/auth/request-code",json=body,headers={"X-Internal-Key":"wrong"}).status_code == 403
    response=client.post("/v1/auth/request-code",json=body,headers={"X-Internal-Key":"internal-secret"})
    assert response.status_code == 202
    assert sent[0]["To"] == "verified-owner@example.com"


def test_independent_institution_emails_its_registered_customer_without_shared_key(mail_context):
    from sqlalchemy import select
    client, settings, models, sent, _, _ = mail_context
    settings.mock_email_recipient_mode = "customer"
    settings.mock_service_api_key = None
    settings.auth_email_recipient = ""
    email = "institution-customer@example.com"
    with client.app.state.session_factory() as session:
        customer = session.scalar(select(models.Customer).where(models.Customer.email == email_for(settings)))
        customer.email = email
        session.commit()
    # A caller cannot redirect even when presenting the old internal-key header.
    response = client.post("/v1/auth/request-code", json={"email": email, "delivery_email": "attacker@example.com"},
                           headers={"X-Internal-Key": "anything"})
    assert response.status_code == 403 and sent == []
    response = client.post("/v1/auth/request-code", json={"email": email})
    assert response.status_code == 202
    assert sent[0]["To"] == email
    code = re.search(r"verification code is: (\d{6})", sent[0].get_content()).group(1)
    token = client.post("/v1/auth/verify-code", json={"email": email, "code": code})
    assert token.status_code == 200
    assert client.get("/v1/customers/me", headers={"Authorization": "Bearer " + token.json()["access_token"]}).json()["email"] == email


def test_customer_mode_core_sends_no_shared_key_or_recipient_override(settings):
    from types import SimpleNamespace
    from backend.app.identity import recipient_payload
    settings.mock_email_recipient_mode = "customer"
    settings.auth_code_delivery = "smtp"
    settings.mock_service_api_key = None
    body, key = recipient_payload(settings, SimpleNamespace(email="app-user@example.com"), {
        "email": "institution-customer@example.com", "delivery_email": "attacker@example.com"})
    assert body == {"email": "institution-customer@example.com"}
    assert key is None
