from datetime import date
from pydantic import Field
from pydantic_settings import SettingsConfigDict
from .mail import MailSettings, MAIL_ENV_FILE


class Settings(MailSettings):
    model_config = SettingsConfigDict(env_file=(MAIL_ENV_FILE, ".env"), extra="ignore")
    lender_id: str = Field(default="mortgages", pattern=r"^[a-z][a-z0-9_-]*$")
    lender_name: str = "Capital Insight Mock Mortgages"
    database_url: str = "sqlite:///./data/mortgages.db"
    data_seed: int = 606
    seed_date: date = date(2026, 11, 1)
    demo_mode: bool = False
    # Judge/tester access (development only): with DEMO_MODE=true and both values set, this one
    # institution customer email always receives TESTER_CODE instead of a random emailed code.
    tester_email: str | None = None
    tester_code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    # Tester consents outlast a judging session; everyone else keeps TOKEN_TTL_SECONDS.
    tester_token_ttl_seconds: int = Field(default=43200, ge=60, le=86400)
    token_ttl_seconds: int = Field(default=1800, ge=1)
    code_ttl_seconds: int = Field(default=300, ge=1)
    code_attempt_limit: int = Field(default=5, ge=1)
    request_cooldown_seconds: int = Field(default=30, ge=1)
    signing_secret: str | None = Field(default=None, min_length=32)
