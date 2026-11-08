"""Environment-backed application configuration."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import SettingsConfigDict
from .mailer import MailSettings, MAIL_ENV_FILE


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(MailSettings):
    model_config = SettingsConfigDict(
        env_file=(MAIL_ENV_FILE, BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core API storage. Use PostgreSQL (e.g. AWS RDS) for shared/deployed environments;
    # SQLite remains only a local fallback. Mock institutions keep their own SQLite files.
    database_url: str = "sqlite:///./data/capital_insight.db"
    # PostgreSQL TLS. RDS hosts default to "require" when unset; use "verify-full" plus the
    # RDS CA bundle (DATABASE_SSLROOTCERT) to also verify the server certificate.
    database_sslmode: Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"] | None = None
    database_sslrootcert: str | None = None
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=5, ge=0, le=50)
    # Recycle before RDS/NAT idle timeouts silently drop connections.
    database_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    database_connect_timeout_seconds: int = Field(default=10, ge=1, le=60)
    encryption_key: SecretStr | None = None
    environment: Literal["development", "production"] = "development"
    session_ttl_seconds: int = Field(default=3600, ge=1)
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
    # Judge/tester sign-in (never in production): this one email always accepts TESTER_CODE,
    # without sending mail. Expiry, attempt limits and single use still apply per request.
    tester_email: str | None = None
    tester_code: SecretStr | None = None
    nvidia_api_key: SecretStr | None = None
    nvidia_model: str = "nvidia/nemotron-3-ultra-550b-a55b"
    nvidia_timeout_seconds: float = Field(default=90, ge=5, le=180)
    nvidia_max_tokens: int = Field(default=2500, ge=256, le=8192)
    nvidia_enable_thinking: bool = False

    # Keep the incoming frontend adapter's settings alongside the core API.
    chase_url: str = "http://localhost:8001"
    amex_url: str = "http://localhost:8002"
    pnc_url: str = "http://localhost:8003"
    discover_url: str = "http://localhost:8004"
    loans_url: str = "http://localhost:8005"
    mortgages_url: str = "http://localhost:8006"
    max_sessions: int = Field(default=10000, ge=1)
    upstream_timeout_seconds: float = Field(default=10.0, gt=0, le=120)

    @model_validator(mode="after")
    def synchronize_upstream_urls(self):
        urls = dict(self.mock_service_urls)
        for provider in ("chase", "amex", "pnc", "discover", "loans", "mortgages"):
            field = f"{provider}_url"
            if field in self.model_fields_set:
                urls[provider] = getattr(self, field)
            elif provider in urls:
                setattr(self, field, urls[provider])
        self.mock_service_urls = self.fixed_upstream_urls(urls)
        return self

    @model_validator(mode="after")
    def tester_code_is_six_digits(self):
        code = self.tester_code.get_secret_value() if self.tester_code else None
        if code is not None and not (len(code) == 6 and code.isdigit()):
            raise ValueError("TESTER_CODE must be exactly six digits")
        return self

    @model_validator(mode="after")
    def production_uses_postgres(self):
        if self.environment == "production" and not self.database_url.startswith(("postgresql", "postgres://")):
            raise ValueError("ENVIRONMENT=production requires a PostgreSQL DATABASE_URL (for example AWS RDS)")
        return self

    @field_validator("database_sslmode", "database_sslrootcert", mode="before")
    @classmethod
    def blank_database_option_is_unset(cls, value):
        return (value.strip() or None) if isinstance(value, str) else value

    @field_validator("encryption_key", "plaid_client_id", "plaid_secret", "nvidia_api_key", "tester_email", "tester_code", mode="before")
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
