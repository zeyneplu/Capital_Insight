"""Optional SMTP delivery for synthetic-customer consent codes."""
from email.message import EmailMessage
import re
import smtplib
import ssl
from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings

# Standalone containers receive these values through environment variables.
# Local services share the repository's ignored .env.mail file.
REPO_ROOT = next((p for p in Path(__file__).resolve().parents if (p / "services" / "mock_bank").is_dir()), Path.cwd())
MAIL_ENV_FILE = REPO_ROOT / ".env.mail"


class MailSettings(BaseSettings):
    mock_email_recipient_mode: Literal["customer", "forwarded_demo"] = "customer"
    mock_service_api_key: SecretStr | None = None
    auth_code_delivery: Literal["log", "smtp"] = "log"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_security: Literal["starttls", "ssl"] = "starttls"
    smtp_username: str = ""
    smtp_password: SecretStr | None = None
    smtp_from: str = ""
    auth_email_recipient: str = ""
    smtp_timeout_seconds: float = Field(default=10, gt=0, le=30)

    @field_validator("smtp_password", "mock_service_api_key", mode="before")
    @classmethod
    def blank_password(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("smtp_from", "auth_email_recipient")
    @classmethod
    def email_address(cls, value: str):
        value = value.strip()
        if value and not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
            raise ValueError("Use one plain email address")
        return value


class MailDeliveryError(Exception):
    """Deliberately omits provider errors, credentials, codes and recipients."""


def validate_mail_configuration(settings: MailSettings) -> None:
    if settings.auth_code_delivery != "smtp" or not all([
        settings.smtp_host, settings.smtp_username, settings.smtp_password, settings.smtp_from,
    ]):
        raise MailDeliveryError("Configure SMTP for user email verification in .env.mail")


def send_user_code(settings: MailSettings, email: str, code: str, ttl_seconds: int) -> None:
    validate_mail_configuration(settings)
    message = EmailMessage()
    message["Subject"] = f"{code} - Capital Insight sign-in"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(f"Your Capital Insight sign-in code is {code}.\n"
        f"It expires in {ttl_seconds // 60} minutes and can be used once.\n"
        "This verifies your email address. Connecting a bank requires a separate authorization.\n"
        "If you did not request this code, ignore this email.")
    context = ssl.create_default_context()
    try:
        if settings.smtp_security == "ssl":
            smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds, context=context)
        else:
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds)
        with smtp:
            if settings.smtp_security == "starttls":
                smtp.ehlo()
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
            if smtp.send_message(message):
                raise MailDeliveryError("Email delivery failed")
    except (OSError, ValueError, smtplib.SMTPException):
        raise MailDeliveryError("Email delivery failed") from None
