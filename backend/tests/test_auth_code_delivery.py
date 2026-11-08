"""AUTH_CODE_DELIVERY modes for Capital Insight's own email sign-in.

The other email tests always configure smtp; these cover the default "log" mode
so local live mode works without SMTP credentials, but never in production.
"""
import logging
import re

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
import pytest

from backend.app import mailer
from backend.app.config import Settings
from backend.app.main import create_app

LOG_LINE = re.compile(r"DEVELOPMENT ONLY Capital Insight sign-in code for (\S+): (\d{6})")


def make_settings(tmp_path, **overrides):
    return Settings(_env_file=None, database_url=f"sqlite:///{tmp_path / 'delivery.db'}",
                    encryption_key=Fernet.generate_key().decode(), plaid_client_id=None, plaid_secret=None,
                    **overrides)


@pytest.fixture
def no_smtp(monkeypatch):
    """Fail the test if anything tries to open an SMTP connection."""
    def refuse(*args, **kwargs):
        raise AssertionError("SMTP must not be used")
    monkeypatch.setattr(mailer.smtplib, "SMTP", refuse)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", refuse)


def test_default_is_log_delivery(tmp_path):
    assert make_settings(tmp_path).auth_code_delivery == "log"


def test_log_mode_signs_in_with_logged_code_in_development(tmp_path, caplog, no_smtp):
    settings = make_settings(tmp_path, environment="development", auth_code_delivery="log")
    email = "Dev.User@Example.com"
    with TestClient(create_app(settings)) as client, caplog.at_level(logging.WARNING, logger="uvicorn.error"):
        response = client.post("/v1/auth/request-email-code", json={"email": email})
        assert response.status_code == 202, response.text
        assert response.json()["delivery"] == "server_log"
        match = LOG_LINE.search(caplog.text)
        assert match, caplog.text
        assert match.group(1) == email.lower()
        code = match.group(2)
        assert code not in response.text
        assert any(r.levelno == logging.WARNING and "DEVELOPMENT ONLY" in r.getMessage() for r in caplog.records)
        token = client.post("/v1/auth/verify-email-code", json={"email": email, "code": code})
        assert token.status_code == 200, token.text
        assert token.json()["access_token"]


def test_log_mode_is_refused_in_production(tmp_path, caplog, no_smtp):
    settings = make_settings(tmp_path, environment="production", auth_code_delivery="log")
    with TestClient(create_app(settings)) as client, caplog.at_level(logging.DEBUG):
        response = client.post("/v1/auth/request-email-code", json={"email": "prod@example.com"})
    assert response.status_code == 503
    assert "DEVELOPMENT ONLY" not in caplog.text
    assert not re.search(r"\b\d{6}\b", response.text)
    with pytest.raises(mailer.MailDeliveryError):
        mailer.send_user_code(settings, "prod@example.com", "123456", 300)
    assert "123456" not in caplog.text


def test_settings_without_environment_fail_closed():
    assert not mailer.log_delivery_enabled(mailer.MailSettings(_env_file=None, auth_code_delivery="log"))


@pytest.mark.parametrize("environment", ["development", "production"])
def test_smtp_mode_still_requires_credentials(tmp_path, caplog, no_smtp, environment):
    settings = make_settings(tmp_path, environment=environment, auth_code_delivery="smtp")
    with TestClient(create_app(settings)) as client, caplog.at_level(logging.DEBUG):
        response = client.post("/v1/auth/request-email-code", json={"email": "user@example.com"})
    assert response.status_code == 503
    assert "DEVELOPMENT ONLY" not in caplog.text


def test_dev_launcher_highlights_sign_in_codes():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "scripts" / "dev.py"
    spec = importlib.util.spec_from_file_location("dev_launcher", path)
    dev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dev)
    for line, email in [
        ("WARNING:  DEVELOPMENT ONLY Capital Insight sign-in code for me@example.com: 042317", "me@example.com"),
        ("WARNING:  DEVELOPMENT ONLY mock consent code for customer1@chase.example.test: 042317", "customer1@chase.example.test"),
    ]:
        match = dev.CODE.search(line)
        assert match and match.groups() == (email, "042317")
