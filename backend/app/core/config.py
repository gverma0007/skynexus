import os
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/skynexus")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ENV: str = os.getenv("ENV", "development")

    # Severity bands for the disruption index (0-100). Tunable via env:
    # SEVERITY_LOW=20 SEVERITY_MEDIUM=40 SEVERITY_HIGH=70
    severity_low: int = int(os.getenv("SEVERITY_LOW", "20"))
    severity_medium: int = int(os.getenv("SEVERITY_MEDIUM", "40"))
    severity_high: int = int(os.getenv("SEVERITY_HIGH", "70"))

    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
