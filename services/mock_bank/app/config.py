from datetime import date
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    bank_id: str = Field(default="chase", pattern=r"^[a-z][a-z0-9_-]*$")
    bank_name: str = "Chase Mock Bank"
    database_url: str = "sqlite:///./data/chase.db"
    data_seed: int = 101
    seed_date: date = date(2026, 11, 1)
    demo_mode: bool = False
    token_ttl_seconds: int = Field(default=1800, ge=1)
    code_ttl_seconds: int = Field(default=300, ge=1)
    code_attempt_limit: int = Field(default=5, ge=1)
    request_cooldown_seconds: int = Field(default=30, ge=1)
    signing_secret: str | None = Field(default=None, min_length=32)
