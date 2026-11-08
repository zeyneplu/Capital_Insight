"""Environment-backed application configuration."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/capital_insight.db"
    encryption_key: SecretStr | None = None
    environment: Literal["development", "production"] = "development"
    session_ttl_seconds: int = Field(default=86400, ge=1)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    request_timeout_seconds: float = Field(default=15, gt=0, le=120)
    mock_service_urls: dict[str, str] = Field(
        default_factory=lambda: {
            "chase": "http://localhost:8001",
            "amex": "http://localhost:8002",
            "pnc": "http://localhost:8003",
            "discover": "http://localhost:8004",
            "loans": "http://localhost:8005",
            "mortgages": "http://localhost:8006",
        }
    )
    plaid_client_id: SecretStr | None = None
    plaid_secret: SecretStr | None = None
    plaid_environment: Literal["sandbox", "production"] = "sandbox"
    plaid_products: list[str] = Field(default_factory=lambda: ["transactions"])
    plaid_country_codes: list[str] = Field(default_factory=lambda: ["US"])
    plaid_redirect_uri: str | None = None

    @field_validator("encryption_key", "plaid_client_id", "plaid_secret", mode="before")
    @classmethod
    def blank_secret_is_unset(cls, value):
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("plaid_redirect_uri", mode="before")
    @classmethod
    def blank_redirect_is_unset(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("mock_service_urls")
    @classmethod
    def fixed_upstream_urls(cls, value: dict[str, str]) -> dict[str, str]:
        from urllib.parse import urlsplit

        for address in value.values():
            parsed = urlsplit(address)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Mock service URLs must be HTTP(S) base URLs without credentials")
        return {provider: address.rstrip("/") for provider, address in value.items()}
