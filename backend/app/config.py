"""Application settings, read from environment variables (server-side only)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "MISSIONFORGE"
    app_version: str = "0.1.0"
    app_contact_email: str = "team@example.com"

    jpl_mdesign_base_url: str = "https://ssd-api.jpl.nasa.gov/mdesign.api"
    jpl_request_timeout_ms: int = 10000
    jpl_cache_ttl_a_seconds: int = 43200
    jpl_cache_ttl_q_seconds: int = 86400
    jpl_cache_ttl_m_seconds: int = 21600

    mission_schema_version: str = "1.0"
    engine_version: str = "0.1.0"
    catalog_version: str = "0.1.0"

    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


# <repo>/data/catalog (backend/app/config.py -> parents[2] is the repo root). Kept here, not in
# the pure domain layer, which only ever receives an explicit path.
DEFAULT_CATALOG_DIR = Path(__file__).resolve().parents[2] / "data" / "catalog"
