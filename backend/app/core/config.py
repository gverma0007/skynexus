"""Runtime settings, read from environment variables (and .env if present)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_db_url(url: str) -> str:
    """Ensure PostgreSQL URL uses the psycopg2 driver."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/skynexus"
    ENV: str = "development"

    # "live" pulls real public feeds; "demo" generates a synthetic 8-day world.
    DATA_MODE: str = "live"
    LIVE_INGEST: int = 1
    LIVE_INGEST_INTERVAL_S: int = 600
    RETENTION_DAYS: int = 8

    # Optional: narrative text for reports. Without a key a deterministic
    # template writes the assessment instead.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-5-5"

    # Disruption index bands (0-100): Calm < low <= Watch < medium <= Elevated < high <= Critical
    SEVERITY_LOW: int = 20
    SEVERITY_MEDIUM: int = 40
    SEVERITY_HIGH: int = 70

    @property
    def severity_low(self) -> int:
        return self.SEVERITY_LOW

    @property
    def severity_medium(self) -> int:
        return self.SEVERITY_MEDIUM

    @property
    def severity_high(self) -> int:
        return self.SEVERITY_HIGH

    @property
    def sqlalchemy_url(self) -> str:
        return normalize_db_url(self.DATABASE_URL)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
