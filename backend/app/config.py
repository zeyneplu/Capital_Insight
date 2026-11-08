from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Upstream mock-service URLs and session limits, read from env or backend/.env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    chase_url: str = "http://localhost:8001"
    amex_url: str = "http://localhost:8002"
    pnc_url: str = "http://localhost:8003"
    discover_url: str = "http://localhost:8004"
    loans_url: str = "http://localhost:8005"
    mortgages_url: str = "http://localhost:8006"
    session_ttl_seconds: int = 3600
    max_sessions: int = 10_000
    upstream_timeout_seconds: float = 10.0
