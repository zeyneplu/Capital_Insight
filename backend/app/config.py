"""All configuration comes from environment variables (12-factor). See .env.example."""

from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BankConfig(BaseModel):
    name: str
    base_url: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # "fixtures" works offline with demo personas; switch to "nessie" once you have a key.
    data_source: Literal["fixtures", "nessie"] = "fixtures"

    nessie_base_url: str = "https://prod-api.nessieisreal.com"
    nessie_api_key: SecretStr | None = None  # SecretStr: never printed in logs or tracebacks

    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_api_key: SecretStr | None = None
    # Copy the exact model ID from the model card on build.nvidia.com.
    nemotron_model: str = "nvidia/nemotron-3-super-120b-a12b"

    # Partner banks (mock-bank instances). Same API, different base_url. JSON in .env.
    banks: dict[str, BankConfig] = {}

    # Postgres for users, bank links, goals. Not used until persistence lands (plan step 4).
    database_url: str | None = None

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
