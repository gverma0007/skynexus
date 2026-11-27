"""Runtime settings, read from environment variables (and .env if present)."""

from functools import lru_cache
from contextvars import ContextVar
from typing import Literal
request_mode = ContextVar("request_mode", default=None)
request_as_of = ContextVar("request_as_of", default=None)

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
    HOSTING_PROFILE: Literal['full', 'free_demo'] = 'full'
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5
    STARTUP_PREPARE: bool = True
    ARCHIVE_MAX_BYTES: int = 64 * 1024 * 1024
    ARCHIVE_MAX_OBJECT_BYTES: int = 8 * 1024 * 1024

    # "live" pulls real public feeds; "demo" generates a synthetic 8-day world.
    DATA_MODE: str = "live"
    LIVE_INGEST: int = 1
    LIVE_INGEST_INTERVAL_S: int = 600
    RETENTION_DAYS: int = 7
    DEMO_EMAIL: str = "demo@skynexus.local"
    DEMO_PASSWORD_HASH: str = ""
    DEMO_DIRECT_LOGIN: bool = False
    COOKIE_SECURE: bool = False
    PUBLIC_ORIGIN: str = "http://localhost:5173"
    REDIS_URL: str = "redis://redis:6379/0"
    AVIATION_INTERVAL_S: int = 120
    AISSTREAM_API_KEY: str = ""
    FIRMS_MAP_KEY: str = ""
    OPENAQ_API_KEY: str = ""
    EIA_API_KEY: str = ""
    CLOUDFLARE_API_TOKEN: str = ""
    GFW_API_TOKEN: str = ""
    EWDS_API_TOKEN: str = ""
    MBTA_API_KEY: str = ""
    ARTIFACT_DIR: str = "artifacts"
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = ""
    ARCHIVE_STORAGE: str = "local"

    @property
    def free_demo(self) -> bool:
        return self.HOSTING_PROFILE == 'free_demo'

    # OpenSky Network OAuth2 credentials (bypasses datacenter IP rate limits on Render/AWS)
    OPENSKY_CLIENT_ID: str = ""
    OPENSKY_CLIENT_SECRET: str = ""
    OPENSKY_USERNAME: str = ""
    OPENSKY_PASSWORD: str = ""

    # Optional: narrative text for reports. Without a key a deterministic
    # template writes the assessment instead.
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = ""

    # Disruption index bands (0-100): Calm < low <= Watch < medium <= Elevated < high <= Critical
    SEVERITY_LOW: int = 20
    SEVERITY_MEDIUM: int = 40
    SEVERITY_HIGH: int = 70

    # Flight route deviation threshold (km)
    FLIGHT_DEVIATION_LIMIT_KM: float = 300.0

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
def base_settings() -> Settings:
    return Settings()

def get_settings() -> Settings:
    cfg = base_settings()
    mode = request_mode.get()
    return cfg.model_copy(update={"DATA_MODE": mode}) if mode in ("live", "demo") else cfg
