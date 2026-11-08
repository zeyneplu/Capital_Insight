"""One codebase, many banks: everything that makes this instance "Pecan Bank" or
"Comet Card" comes from environment variables. See .env.example."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET = "dev-only-change-me"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bank_id: str = Field(default="pecan", pattern=r"^[a-z0-9-]{2,32}$")
    bank_name: str = "Pecan Bank (demo)"
    seed: int = 42  # same seed -> identical data on every replica of this bank
    customers_file: Path = PACKAGE_ROOT / "data" / "customers.json"
    history_days: int = Field(default=90, ge=1, le=730)

    # Default: one SQLite file per bank. Any SQLAlchemy URL works (e.g. Postgres on AWS).
    database_url: str | None = None

    # Signs OTP and token hashes. Must be changed outside dev mode.
    bank_secret: SecretStr = SecretStr(DEFAULT_SECRET)
    # Dev mode exposes GET /dev/outbox so you can read "emails" without an email server.
    dev_mode: bool = True

    otp_ttl_minutes: int = Field(default=10, ge=0)
    otp_max_attempts: int = Field(default=5, ge=1)
    token_ttl_minutes: int = Field(default=24 * 60, ge=1)

    @property
    def resolved_database_url(self) -> str:
        return self.database_url or f"sqlite:///data/{self.bank_id}.db"

    def check_safe_to_run(self) -> None:
        if not self.dev_mode and self.bank_secret.get_secret_value() == DEFAULT_SECRET:
            raise RuntimeError("Set BANK_SECRET when DEV_MODE=false")
